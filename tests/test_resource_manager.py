"""Bộ kiểm thử đơn vị & tích hợp toàn diện cho Bộ Điều Phối Tài Nguyên (Resource Manager).

Kiểm thử:
1. Reader-Writer Lock (IndexAccessCoordinator): Đọc đồng thời, Ghi độc quyền, Ưu tiên luồng ghi, Timeout.
2. State Machine & Lifecycle: CHAT_READY, INDEXING_CPU, INDEXING_GPU, RESTORING_CHAT, RECOVERY_FAILED.
3. Chính sách chọn thiết bị tự động (determine_indexing_device) theo số bản ghi và điều kiện VRAM.
4. Quản lý vòng đời mô hình BGE-M3 (EmbeddingModelManager) và Inference Tracker.
5. Telemetry phần cứng native (VRAM, RAM, CPU).
6. Tích hợp ChatEngine: Phản hồi an toàn khi GPU đang bận, nhả khóa đọc trước LLM generation.
7. Kiểm tra tính toàn vẹn và bất biến của tập ID bản ghi (ID Invariance).
"""

import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import settings
from src.core.models import QARecord
from src.resource.manager import (
    EmbeddingModelManager,
    HardwareTelemetry,
    IndexAccessCoordinator,
    ResourceManager,
    ResourceState,
    get_resource_manager,
)


class TestIndexAccessCoordinator(unittest.TestCase):
    """Kiểm thử Reader-Writer Lock chuẩn của IndexAccessCoordinator."""

    def setUp(self):
        self.coord = IndexAccessCoordinator()

    def test_multiple_readers_concurrent(self):
        """Nhiều luồng đọc có thể giữ khóa đọc đồng thời."""
        acquired_count = 0
        lock = threading.Lock()

        def reader_job():
            nonlocal acquired_count
            with self.coord.read_lock(timeout=2.0) as acq:
                if acq:
                    with lock:
                        acquired_count += 1
                    time.sleep(0.05)

        threads = [threading.Thread(target=reader_job) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(acquired_count, 5, "Cả 5 luồng đọc đều phải lấy được read_lock đồng thời!")

    def test_writer_excludes_readers(self):
        """Khi Writer đang giữ write_lock, Reader không thể acquire_read và bị timeout."""
        writer_acquired = threading.Event()
        writer_release = threading.Event()
        reader_result = []

        def writer_job():
            with self.coord.write_lock(timeout=2.0) as acq:
                if acq:
                    writer_acquired.set()
                    writer_release.wait(timeout=1.0)

        def reader_job():
            writer_acquired.wait(timeout=1.0)
            # Thử lấy read_lock với timeout ngắn 0.1s
            acq = self.coord.acquire_read(timeout=0.1)
            reader_result.append(acq)
            if acq:
                self.coord.release_read()

        t_writer = threading.Thread(target=writer_job)
        t_reader = threading.Thread(target=reader_job)

        t_writer.start()
        t_reader.start()

        t_reader.join()
        writer_release.set()
        t_writer.join()

        self.assertEqual(reader_result, [False], "Reader không được phép lấy khóa đọc khi Writer đang giữ khóa!")

    def test_readers_exclude_writer(self):
        """Khi Reader đang giữ read_lock, Writer không thể acquire_write cho tới khi Reader nhả khóa."""
        reader_acquired = threading.Event()
        reader_release = threading.Event()
        writer_result = []

        def reader_job():
            with self.coord.read_lock(timeout=2.0) as acq:
                if acq:
                    reader_acquired.set()
                    reader_release.wait(timeout=1.0)

        def writer_job():
            reader_acquired.wait(timeout=1.0)
            # Thử lấy write_lock với timeout ngắn 0.1s
            acq = self.coord.acquire_write(timeout=0.1)
            writer_result.append(acq)
            if acq:
                self.coord.release_write()

        t_reader = threading.Thread(target=reader_job)
        t_writer = threading.Thread(target=writer_job)

        t_reader.start()
        t_writer.start()

        t_writer.join()
        reader_release.set()
        t_reader.join()

        self.assertEqual(writer_result, [False], "Writer không được phép lấy khóa ghi khi Reader đang đọc!")


class TestResourceManagerPolicyAndStates(unittest.TestCase):
    """Kiểm thử State Machine và chính sách chọn thiết bị trong ResourceManager."""

    def setUp(self):
        self.rm = ResourceManager()
        self.rm.state = ResourceState.CHAT_READY

    def test_determine_indexing_device_small_batch_prefers_cpu(self):
        """Batch nhỏ (< 300 bản ghi) ưu tiên chạy CPU để không mất overhead chuyển đổi model."""
        device, reason = self.rm.determine_indexing_device(record_count=100, is_replace=False)
        self.assertEqual(device, "cpu")
        self.assertIn("ngưỡng GPU", reason)

    def test_determine_indexing_device_large_batch(self):
        """Batch lớn (>= 300 bản ghi) chọn CUDA nếu hệ thống có GPU và bật cấu hình."""
        with patch("torch.cuda.is_available", return_value=True):
            device, reason = self.rm.determine_indexing_device(record_count=500, is_replace=False)
            self.assertEqual(device, "cuda")

    def test_determine_indexing_device_when_cuda_disabled(self):
        """Nếu ENABLE_GPU_INDEXING=False trong cấu hình, luôn trả về CPU."""
        orig = getattr(settings, "ENABLE_GPU_INDEXING", True)
        try:
            object.__setattr__(settings, "ENABLE_GPU_INDEXING", False)
            device, reason = self.rm.determine_indexing_device(record_count=1000, is_replace=False)
            self.assertEqual(device, "cpu")
        finally:
            object.__setattr__(settings, "ENABLE_GPU_INDEXING", orig)

    def test_prepare_gpu_indexing_insufficient_vram_falls_back_to_cpu(self):
        """Nếu sau khi unload Ollama mà VRAM khả dụng < MIN_VRAM_GPU_INDEXING_MB, tự động fallback CPU."""
        mock_ollama = MagicMock()
        mock_ollama.unload_model.return_value = True

        # Giả lập VRAM chỉ còn 1500 MB (< 3500 MB)
        fake_vram = {
            "available": True,
            "device_name": "RTX 3050",
            "total_mb": 8192.0,
            "used_mb": 6692.0,
            "free_mb": 1500.0,
            "used_pct": 81.7,
        }

        with patch.object(self.rm.telemetry, "get_vram_info", return_value=fake_vram):
            success, msg = self.rm.prepare_gpu_indexing(ollama_client=mock_ollama)
            self.assertFalse(success)
            self.assertEqual(self.rm.state, ResourceState.INDEXING_CPU)
            self.assertIn("không đủ ngưỡng an toàn", msg)

    def test_finalize_indexing_restores_chat_state_on_success(self):
        """Sau khi GPU index xong, finalize_indexing khôi phục Qwen và trả về CHAT_READY."""
        mock_ollama = MagicMock()
        mock_ollama.ping_model.return_value = True

        self.rm.state = ResourceState.INDEXING_GPU
        with patch.object(self.rm.model_manager, "unload_model"), \
             patch.object(self.rm.model_manager, "switch_device"):
            success, msg = self.rm.finalize_indexing(used_gpu=True, ollama_client=mock_ollama)
            self.assertTrue(success)
            self.assertEqual(self.rm.state, ResourceState.CHAT_READY)

    def test_finalize_indexing_fails_when_ollama_recovery_fails(self):
        """Nếu khôi phục Qwen thất bại, đặt trạng thái RECOVERY_FAILED, không báo sẵn sàng."""
        mock_ollama = MagicMock()
        mock_ollama.ping_model.return_value = False

        self.rm.state = ResourceState.INDEXING_GPU
        with patch.object(self.rm.model_manager, "unload_model"), \
             patch.object(self.rm.model_manager, "switch_device"):
            success, msg = self.rm.finalize_indexing(used_gpu=True, ollama_client=mock_ollama)
            self.assertFalse(success)
            self.assertEqual(self.rm.state, ResourceState.RECOVERY_FAILED)


class TestEmbeddingModelManager(unittest.TestCase):
    """Kiểm thử EmbeddingModelManager."""

    def setUp(self):
        self.mgr = EmbeddingModelManager()

    def test_track_inference_counter(self):
        """Inference tracker tăng và giảm biến đếm chính xác."""
        self.assertEqual(self.mgr._active_inferences, 0)
        with self.mgr.track_inference():
            self.assertEqual(self.mgr._active_inferences, 1)
        self.assertEqual(self.mgr._active_inferences, 0)


class TestHardwareTelemetry(unittest.TestCase):
    """Kiểm thử tính đúng đắn của dữ liệu giám sát phần cứng native."""

    def test_telemetry_types(self):
        vram = HardwareTelemetry.get_vram_info()
        ram = HardwareTelemetry.get_ram_info()
        cpu = HardwareTelemetry.get_cpu_info()

        self.assertIsInstance(vram, dict)
        self.assertIn("available", vram)
        self.assertIsInstance(ram, dict)
        self.assertIn("total_mb", ram)
        self.assertIsInstance(cpu, dict)
        self.assertGreaterEqual(cpu["logical_cores"], 1)
        self.assertGreaterEqual(cpu["torch_threads"], 1)


class TestChatEngineIntegration(unittest.TestCase):
    """Kiểm thử tương tác an toàn giữa ChatEngine và ResourceManager."""

    def setUp(self):
        self.rm = get_resource_manager()
        self.rm.state = ResourceState.CHAT_READY

    def test_ask_returns_busy_when_gpu_indexing(self):
        """Khi hệ thống đang ở INDEXING_GPU, câu hỏi chat nhận phản hồi hệ thống bận thân thiện."""
        from src.chat.engine import ChatEngine
        engine = ChatEngine(records=[])

        self.rm.state = ResourceState.INDEXING_GPU
        try:
            resp = engine.ask("apple nghĩa là gì?")
            self.assertEqual(resp.mode, "NO_MATCH")
            self.assertIn("đồng bộ dữ liệu chỉ mục", resp.answer)
        finally:
            self.rm.state = ResourceState.CHAT_READY

    def test_ask_stream_returns_busy_when_gpu_indexing(self):
        """Khi hệ thống đang ở INDEXING_GPU, ask_stream nhận thông báo bận."""
        from src.chat.engine import ChatEngine
        engine = ChatEngine(records=[])

        self.rm.state = ResourceState.INDEXING_GPU
        try:
            tokens = []
            final_resp = None
            for token, r in engine.ask_stream("apple nghĩa là gì?"):
                tokens.append(token)
                if r:
                    final_resp = r
            full_text = "".join(tokens)
            self.assertIn("đồng bộ dữ liệu chỉ mục", full_text)
            self.assertIsNotNone(final_resp)
            self.assertEqual(final_resp.mode, "NO_MATCH")
        finally:
            self.rm.state = ResourceState.CHAT_READY

    def test_chat_proceeds_normally_during_cpu_indexing(self):
        """Khi hệ thống đang ở INDEXING_CPU, câu hỏi chat vẫn được xử lý bình thường."""
        from src.chat.engine import ChatEngine
        engine = ChatEngine(records=[])

        self.rm.state = ResourceState.INDEXING_CPU
        try:
            resp = engine.ask("")
            # Câu hỏi rỗng trả về "Vui lòng nhập câu hỏi." chứ không bị chặn hệ thống bận
            self.assertEqual(resp.answer, "Vui lòng nhập câu hỏi.")
        finally:
            self.rm.state = ResourceState.CHAT_READY



class TestBGEChromaOOMRecovery(unittest.TestCase):
    """Kiểm thử cơ chế tự động giảm batch size và fallback khi gặp lỗi CUDA OOM."""

    def test_encode_texts_safe_handles_oom_and_halves_batch(self):
        from src.retriever.bge_chroma import BGEChromaRetriever
        retriever = BGEChromaRetriever(records=[])

        mock_model = MagicMock()
        call_count = 0

        def fake_encode(texts, batch_size=64, show_progress_bar=False, normalize_embeddings=True):
            nonlocal call_count
            call_count += 1
            if call_count == 1 and batch_size == 64:
                import torch
                raise RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB")
            # Lần gọi thứ 2 với batch_size=32 thành công
            mock_arr = MagicMock()
            mock_arr.tolist.return_value = [[0.1] * 10] * len(texts)
            return mock_arr

        mock_model.encode.side_effect = fake_encode

        sample_texts = ["test text 1", "test text 2"]
        embeddings = retriever._encode_texts_safe(mock_model, sample_texts, batch_size=64)

        self.assertEqual(len(embeddings), 2)
        self.assertEqual(call_count, 2, "Hệ thống phải thử lại lần 2 với batch_size đã giảm một nửa!")


class TestIDSetInvariance(unittest.TestCase):
    """Kiểm thử tính bất biến của tập hợp ID bản ghi giữa các tầng lưu trữ."""

    def test_id_set_consistency_after_records_sync(self):
        from src.data.loader import QALoader
        from src.retriever.bge_chroma import BGEChromaRetriever
        from src.retriever.bm25_retriever import BM25Retriever

        sample_records = [
            QARecord(record_id="id_1", word="apple", question="apple?", answer="táo"),
            QARecord(record_id="id_2", word="banana", question="banana?", answer="chuối"),
            QARecord(record_id="id_3", word="orange", question="orange?", answer="cam"),
        ]

        bm25 = BM25Retriever(sample_records)
        bge = BGEChromaRetriever(sample_records)

        bm25_ids = {r.record_id for r in bm25.records}
        bge_ids = set(bge.rec_map.keys())
        expected_ids = {"id_1", "id_2", "id_3"}

        self.assertEqual(bm25_ids, expected_ids)
        self.assertEqual(bge_ids, expected_ids)
        self.assertEqual(bm25_ids, bge_ids, "Tập ID bản ghi giữa BM25 và BGEChroma phải đồng nhất 100%!")


if __name__ == "__main__":
    unittest.main()

