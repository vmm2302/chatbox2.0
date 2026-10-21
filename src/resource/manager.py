"""Module điều phối và tối ưu hóa tài nguyên phần cứng (Resource Manager).

Chịu trách nhiệm:
1. State Machine: CHAT_READY, INDEXING_CPU, INDEXING_GPU, RESTORING_CHAT, RECOVERY_FAILED.
2. Reader-Writer Lock (IndexAccessCoordinator): Phân tách rành mạch truy xuất đọc song song và ghi độc quyền.
3. Model Provider (EmbeddingModelManager): Quản lý tập trung vòng đời BGE-M3, chuyển đổi thiết bị an toàn.
4. Native Hardware Telemetry: Giám sát RAM (Windows ctypes), VRAM (Torch CUDA), CPU threads không phụ thuộc thư viện ngoài.
5. Qwen / Ollama Lifecycle Coordination: Giải phóng VRAM khi nạp batch lớn và khôi phục an toàn.
"""

import ctypes
import gc
import logging
import os
import platform
import threading
import time
from contextlib import contextmanager
from enum import Enum
from typing import Any, Dict, Generator, List, Optional, Tuple

from config.settings import settings

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. TRẠNG THÁI HỆ THỐNG (RESOURCE STATES)
# ==============================================================================

class ResourceState(str, Enum):
    CHAT_READY = "CHAT_READY"              # Chatbot sẵn sàng, ưu tiên Qwen trên GPU, BGE trên CPU
    INDEXING_CPU = "INDEXING_CPU"          # Đang nạp dữ liệu trên CPU, Chatbot vẫn phục vụ an toàn
    INDEXING_GPU = "INDEXING_GPU"          # Đang nạp batch lớn trên GPU, Qwen tạm thời được unload
    RESTORING_CHAT = "RESTORING_CHAT"      # Đang khôi phục lại Qwen và kiểm tra tính sẵn sàng
    RECOVERY_FAILED = "RECOVERY_FAILED"    # Lỗi khi khôi phục Qwen, cần kiểm tra kỹ thuật


# ==============================================================================
# 2. KHÓA BẢO VỆ CHỈ MỤC & DỮ LIỆU (READER-WRITER LOCK)
# ==============================================================================

class IndexAccessCoordinator:
    """Điều phối truy cập chỉ mục theo mô hình Reader-Writer Lock chuẩn.

    - Cho phép nhiều luồng đọc (Chat query search) hoạt động song song.
    - Đảm bảo duy nhất một luồng ghi (Ingestion commit) được độc quyền thay đổi dữ liệu.
    - Ưu tiên luồng ghi (Writer-preference) để tránh Writer bị bỏ đói vô tận khi có nhiều Readers liên tục.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._readers: int = 0
        self._writer: bool = False
        self._writer_thread: Optional[int] = None
        self._writer_recursion: int = 0
        self._waiting_writers: int = 0

    def acquire_read(self, timeout: float = 10.0) -> bool:
        """Xin khóa đọc (cho phép đọc đồng thời). Trả về True nếu thành công, False nếu timeout."""
        current_thread = threading.get_ident()
        deadline = time.time() + timeout
        with self._lock:
            # Nếu chính luồng writer đang giữ khóa ghi, cho phép đọc đệ quy
            if self._writer and self._writer_thread == current_thread:
                self._readers += 1
                return True

            while self._writer or self._waiting_writers > 0:
                remaining = deadline - time.time()
                if remaining <= 0:
                    return False
                self._condition.wait(timeout=remaining)
            self._readers += 1
            return True

    def release_read(self) -> None:
        """Nhả khóa đọc."""
        with self._lock:
            if self._readers > 0:
                self._readers -= 1
                if self._readers == 0:
                    self._condition.notify_all()

    def acquire_write(self, timeout: float = 30.0) -> bool:
        """Xin khóa ghi độc quyền. Hỗ trợ re-entrant cho cùng một luồng ghi. Trả về True nếu thành công, False nếu timeout."""
        current_thread = threading.get_ident()
        deadline = time.time() + timeout
        with self._lock:
            # Nếu chính luồng này đã giữ khóa ghi, tăng biến đếm đệ quy và cho qua
            if self._writer and self._writer_thread == current_thread:
                self._writer_recursion += 1
                return True

            self._waiting_writers += 1
            try:
                while self._writer or self._readers > 0:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        return False
                    self._condition.wait(timeout=remaining)
                self._writer = True
                self._writer_thread = current_thread
                self._writer_recursion = 1
                return True
            finally:
                self._waiting_writers -= 1

    def release_write(self) -> None:
        """Nhả khóa ghi độc quyền."""
        current_thread = threading.get_ident()
        with self._lock:
            if self._writer and self._writer_thread == current_thread:
                self._writer_recursion -= 1
                if self._writer_recursion <= 0:
                    self._writer = False
                    self._writer_thread = None
                    self._writer_recursion = 0
                    self._condition.notify_all()

    @contextmanager
    def read_lock(self, timeout: float = 10.0) -> Generator[bool, None, None]:
        """Context manager cho khóa đọc."""
        acquired = self.acquire_read(timeout=timeout)
        try:
            yield acquired
        finally:
            if acquired:
                self.release_read()

    @contextmanager
    def write_lock(self, timeout: float = 30.0) -> Generator[bool, None, None]:
        """Context manager cho khóa ghi."""
        acquired = self.acquire_write(timeout=timeout)
        try:
            yield acquired
        finally:
            if acquired:
                self.release_write()


# ==============================================================================
# 3. QUẢN LÝ VÒNG ĐỜI MODEL BGE-M3 TẬP TRUNG (SHARED EMBEDDING MODEL PROVIDER)
# ==============================================================================

class EmbeddingModelManager:
    """Quản lý một đối tượng mô hình BGE-M3 duy nhất, điều phối nạp và giải phóng CUDA an toàn."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.BGE_M3_MODEL_NAME
        self._model = None
        self._current_device: str = "cpu"
        self._model_lock = threading.RLock()
        self._active_inferences: int = 0
        self._inference_cond = threading.Condition(self._model_lock)

    @property
    def current_device(self) -> str:
        return self._current_device

    def is_loaded(self) -> bool:
        return self._model is not None

    def get_model(self, preferred_device: Optional[str] = None):
        """Lấy đối tượng mô hình SentenceTransformer, nạp hoặc chuyển thiết bị nếu cần."""
        from sentence_transformers import SentenceTransformer

        target_dev = (preferred_device or self._current_device or "cpu").strip().lower()
        if target_dev in ("gpu", "cuda"):
            import torch
            target_dev = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            target_dev = "cpu"

        with self._model_lock:
            if self._model is not None and self._current_device == target_dev:
                return self._model

            # Nếu model đang nạp trên thiết bị khác, cần chuyển đổi an toàn
            self.switch_device(target_dev)
            return self._model

    def switch_device(self, target_device: str) -> None:
        """Chuyển đổi thiết bị thực thi của BGE-M3 một cách an toàn."""
        from sentence_transformers import SentenceTransformer

        clean_dev = target_device.strip().lower()
        if clean_dev in ("gpu", "cuda"):
            import torch
            clean_dev = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            clean_dev = "cpu"

        with self._model_lock:
            # 1. Chờ cho tất cả các tác vụ inference đang chạy hoàn tất
            while self._active_inferences > 0:
                self._inference_cond.wait(timeout=0.1)

            # 2. Nếu model đã nạp trên thiết bị cũ, thu hồi và giải phóng triệt để
            if self._model is not None:
                logger.info(
                    "Đang giải phóng BGE-M3 khỏi thiết bị '%s' để chuyển sang '%s'...",
                    self._current_device,
                    clean_dev
                )
                del self._model
                self._model = None
                gc.collect()
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass

            # 3. Nạp model trên thiết bị mới
            logger.info("Đang nạp BGE-M3 lên thiết bị: %s", clean_dev)
            try:
                self._model = SentenceTransformer(
                    self.model_name,
                    device=clean_dev,
                    local_files_only=True
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Không thể nạp mô hình BGE-M3 '{self.model_name}' từ local cache: {exc}. "
                    "Hệ thống đang hoạt động ở chế độ OFFLINE nghiêm ngặt, không tự ý tải model qua mạng trong runtime. "
                    "Vui lòng tải model trước qua script: 'python scripts/download_models.py' hoặc tham khảo HUONG_DAN_CAI_DAT_MAY_MOI.md."
                ) from exc
            self._current_device = clean_dev
            logger.info("BGE-M3 đã sẵn sàng hoạt động trên thiết bị: %s", clean_dev)

    def unload_model(self) -> None:
        """Giải phóng hoàn toàn model khỏi bộ nhớ (cả RAM và VRAM)."""
        with self._model_lock:
            while self._active_inferences > 0:
                self._inference_cond.wait(timeout=0.1)

            if self._model is not None:
                logger.info("Đang dọn dẹp BGE-M3 khỏi %s...", self._current_device)
                del self._model
                self._model = None
                gc.collect()
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass
                self._current_device = "cpu"

    @contextmanager
    def track_inference(self) -> Generator[None, None, None]:
        """Context manager theo dõi các lượt tính toán inference để tránh giải phóng khi đang tính toán."""
        with self._model_lock:
            self._active_inferences += 1
        try:
            yield
        finally:
            with self._model_lock:
                self._active_inferences = max(0, self._active_inferences - 1)
                if self._active_inferences == 0:
                    self._inference_cond.notify_all()


# ==============================================================================
# 4. GIÁM SÁT TÀI NGUYÊN NATIVE (HARDWARE TELEMETRY KHÔNG DEPENDENCY MỚI)
# ==============================================================================

class HardwareTelemetry:
    """Cung cấp các số liệu đo lường phần cứng trực tiếp từ OS và Torch."""

    @staticmethod
    def get_vram_info() -> Dict[str, Any]:
        """Đo lường VRAM động qua PyTorch CUDA."""
        try:
            import torch
            if torch.cuda.is_available():
                free_bytes, total_bytes = torch.cuda.mem_get_info(0)
                used_bytes = total_bytes - free_bytes
                return {
                    "available": True,
                    "device_name": torch.cuda.get_device_name(0),
                    "total_mb": round(total_bytes / (1024 ** 2), 1),
                    "used_mb": round(used_bytes / (1024 ** 2), 1),
                    "free_mb": round(free_bytes / (1024 ** 2), 1),
                    "used_pct": round((used_bytes / total_bytes) * 100, 1),
                }
        except Exception as exc:
            logger.debug("Không thể đọc thông tin VRAM: %s", exc)

        return {
            "available": False,
            "device_name": "N/A",
            "total_mb": 0.0,
            "used_mb": 0.0,
            "free_mb": 0.0,
            "used_pct": 0.0,
        }

    @staticmethod
    def get_ram_info() -> Dict[str, Any]:
        """Đo lường RAM trên Windows thông qua ctypes (chuẩn thư viện Python)."""
        if platform.system() == "Windows":
            try:
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]

                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    total_mb = stat.ullTotalPhys / (1024 ** 2)
                    free_mb = stat.ullAvailPhys / (1024 ** 2)
                    used_mb = total_mb - free_mb
                    return {
                        "total_mb": round(total_mb, 1),
                        "used_mb": round(used_mb, 1),
                        "free_mb": round(free_mb, 1),
                        "load_pct": int(stat.dwMemoryLoad),
                    }
            except Exception as exc:
                logger.debug("Không thể đọc RAM qua ctypes Windows: %s", exc)

        return {
            "total_mb": 0.0,
            "used_mb": 0.0,
            "free_mb": 0.0,
            "load_pct": 0,
        }

    @staticmethod
    def get_cpu_info() -> Dict[str, Any]:
        """Thông số CPU và số luồng Torch."""
        import torch
        logical_cores = os.cpu_count() or 4
        torch_threads = torch.get_num_threads()
        return {
            "logical_cores": logical_cores,
            "torch_threads": torch_threads,
        }


# ==============================================================================
# 5. BỘ ĐIỀU PHỐI TÀI NGUYÊN TOÀN CỤC (PROCESS-LEVEL SINGLETON RESOURCE MANAGER)
# ==============================================================================

class ResourceManager:
    """Bộ điều phối tài nguyên trung tâm cho toàn bộ ứng dụng Chatbox 2.0."""

    _instance: Optional["ResourceManager"] = None
    _init_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.state: ResourceState = ResourceState.CHAT_READY
        self.transition_lock = threading.Lock()
        self.coordinator = IndexAccessCoordinator()
        self.model_manager = EmbeddingModelManager()
        self.telemetry = HardwareTelemetry()
        self.last_error: Optional[str] = None
        self.last_transition_time: float = time.time()
        self.last_indexing_duration: float = 0.0

        # Cố định số luồng tính toán CPU của PyTorch duy nhất 1 lần lúc khởi động hệ thống
        self._configure_torch_threads()

    def _configure_torch_threads(self) -> None:
        """Thiết lập số luồng PyTorch CPU an toàn (tránh CPU 100% starvation)."""
        try:
            import torch
            target_threads = int(getattr(settings, "CPU_NUM_THREADS", 4))
            max_cores = os.cpu_count() or 4
            clamped = max(1, min(target_threads, max_cores))
            torch.set_num_threads(clamped)
            logger.info("Đã cấu hình số luồng PyTorch CPU cố định: %d luồng", clamped)
        except Exception as exc:
            logger.warning("Không thể cấu hình luồng PyTorch: %s", exc)

    def determine_indexing_device(self, record_count: int, is_replace: bool = False) -> Tuple[str, str]:
        """Quyết định sơ bộ thiết bị lập chỉ mục dựa trên số bản ghi và cấu hình."""
        import torch

        if not getattr(settings, "ENABLE_GPU_INDEXING", True):
            return "cpu", "Cấu hình ENABLE_GPU_INDEXING=False"

        if not torch.cuda.is_available():
            return "cpu", "CUDA không khả dụng trên máy tính"

        min_records = int(getattr(settings, "GPU_INDEXING_MIN_RECORDS", 300))
        if record_count < min_records and not is_replace:
            return "cpu", f"Số bản ghi ({record_count}) < ngưỡng GPU ({min_records}). Chạy CPU nhanh hơn do không tốn overhead chuyển đổi."

        return "cuda", f"Số bản ghi ({record_count}) >= {min_records}, thỏa mãn điều kiện tăng tốc GPU."

    def prepare_gpu_indexing(self, ollama_client: Optional[Any] = None) -> Tuple[bool, str]:
        """Quy trình chuẩn bị GPU an toàn:
        1. Khóa chuyển đổi trạng thái
        2. Unload Qwen khỏi VRAM qua Ollama
        3. Đo lại VRAM thực tế
        4. Kiểm tra headroom an toàn >= MIN_VRAM_GPU_INDEXING_MB (3500MB)
        5. Nạp BGE-M3 lên CUDA
        """
        with self.transition_lock:
            self.state = ResourceState.INDEXING_GPU
            self.last_transition_time = time.time()
            logger.info("Bắt đầu quy trình chuẩn bị INDEXING_GPU...")

            # 1. Unload Qwen khỏi Ollama
            if ollama_client is not None and hasattr(ollama_client, "unload_model"):
                unloaded = ollama_client.unload_model()
                if not unloaded:
                    logger.warning("Không thể unload Qwen qua Ollama API. Kiểm tra lại VRAM...")
                time.sleep(1.0)  # Chờ driver giải phóng bộ nhớ

            # 2. Đo lại VRAM thực tế
            vram = self.telemetry.get_vram_info()
            min_vram = float(getattr(settings, "MIN_VRAM_GPU_INDEXING_MB", 3500))

            if not vram["available"] or vram["free_mb"] < min_vram:
                err_msg = (
                    f"VRAM còn trống ({vram['free_mb']} MB) không đủ ngưỡng an toàn ({min_vram} MB). "
                    "Tự động chuyển sang INDEXING_CPU để tránh lỗi OOM."
                )
                logger.warning(err_msg)
                self.state = ResourceState.INDEXING_CPU
                self.last_error = err_msg
                # Khôi phục lại Qwen nếu cần
                if ollama_client is not None and hasattr(ollama_client, "ping_model"):
                    ollama_client.ping_model()
                return False, err_msg

            # 3. Nạp BGE-M3 lên CUDA
            try:
                self.model_manager.switch_device("cuda")
                logger.info("Đã chuyển BGE-M3 lên GPU CUDA thành công.")
                return True, "GPU sẵn sàng"
            except Exception as exc:
                err_msg = f"Lỗi khi nạp BGE-M3 lên CUDA: {exc}. Tự động fallback sang CPU."
                logger.error(err_msg)
                self.state = ResourceState.INDEXING_CPU
                self.last_error = err_msg
                self.model_manager.switch_device("cpu")
                return False, err_msg

    def finalize_indexing(self, used_gpu: bool, ollama_client: Optional[Any] = None) -> Tuple[bool, str]:
        """Quy trình hoàn tất indexing:
        - Nếu dùng GPU: Giải phóng BGE-M3, nạp lại Qwen vào Ollama, ping kiểm tra và chuyển về CHAT_READY.
        - Nếu dùng CPU: Chuyển về CHAT_READY.
        """
        with self.transition_lock:
            if not used_gpu:
                self.state = ResourceState.CHAT_READY
                self.last_transition_time = time.time()
                return True, "Hoàn tất lập chỉ mục trên CPU. Chatbot sẵn sàng."

            # Chuyển sang RESTORING_CHAT
            self.state = ResourceState.RESTORING_CHAT
            self.last_transition_time = time.time()
            logger.info("Đang chuyển sang trạng thái RESTORING_CHAT...")

            # 1. Giải phóng BGE-M3 khỏi CUDA
            self.model_manager.unload_model()

            # 2. Đưa BGE-M3 về thiết bị mặc định của Chat (mặc định CPU)
            chat_device = getattr(settings, "EMBEDDING_CHAT_DEVICE", "cpu")
            try:
                self.model_manager.switch_device(chat_device)
            except Exception as exc:
                logger.warning("Không thể nạp BGE-M3 về chat device '%s': %s", chat_device, exc)

            # 3. Khôi phục Qwen trong Ollama và kiểm tra sẵn sàng
            recovered = True
            if ollama_client is not None and hasattr(ollama_client, "ping_model"):
                recovered = ollama_client.ping_model(timeout=25.0)

            if recovered:
                self.state = ResourceState.CHAT_READY
                self.last_transition_time = time.time()
                logger.info("Đã khôi phục hoàn tất Qwen2.5:7B. Chatbot đã sẵn sàng (CHAT_READY).")
                return True, "Khôi phục thành công. Chatbot đã sẵn sàng."
            else:
                self.state = ResourceState.RECOVERY_FAILED
                self.last_error = "Không thể kích hoạt lại mô hình Qwen trong Ollama sau khi nạp dữ liệu."
                logger.error("Khôi phục Qwen thất bại! Đặt trạng thái RECOVERY_FAILED.")
                return False, self.last_error


# Khởi tạo singleton dùng chung
_global_resource_manager: Optional[ResourceManager] = None
_rm_lock = threading.Lock()


def get_resource_manager() -> ResourceManager:
    """Lấy singleton ResourceManager cấp tiến trình."""
    global _global_resource_manager
    with _rm_lock:
        if _global_resource_manager is None:
            _global_resource_manager = ResourceManager()
        return _global_resource_manager
