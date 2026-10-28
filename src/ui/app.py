"""Giao diện Web Chatbox 2.0 phát triển trên Streamlit.

Hệ thống tra cứu từ vựng tiếng Anh bằng tiếng Việt chuẩn kiến trúc Web Desktop-style:
- Sidebar bên trái: Logo Chatbox 2.0, Nút '+ Cuộc trò chuyện mới', Menu điều hướng 3 trang.
- Khung chính:
  1. Trang 'Tra cứu từ vựng': Tiêu đề kèm badge 'Local', vùng tin nhắn cuộn tự nhiên theo viewport,
     lượt người dùng căn phải kèm icon trong bong bóng xám nhạt, lượt chatbot đóng khung trong card có viền nhẹ,
     expander nguồn dữ liệu thật, ô nhập st.chat_input ở đáy.
  2. Trang 'Quản lý dữ liệu': Nạp đa tệp (8 định dạng), phân tách ADD/REPLACE kèm xác nhận an toàn, thống kê lưu trữ.
  3. Trang 'Chẩn đoán': Thông số động GPU/CUDA, phân biệt model Ollama, System Prompt read-only, công tắc Inspector, audit log.
"""

import base64
import html
import json
import logging
import os
import shutil
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

# Đo lường thời điểm nạp tiến trình ứng dụng
_T_APP_START = time.perf_counter()
perf_logger = logging.getLogger("chatbox.perf")

# Type checking hints không gây import nặng ở runtime
if TYPE_CHECKING:
    from src.chat.engine import ChatEngine
    from src.data.batch_ingestion import BatchIngestionManager, BatchStatus, FileStatus
    from src.data.loaders.sqlite_loader import (
        SQLiteLoader,
        SQLiteMappingConfig,
        SQLiteMappingMode,
        SQLiteSchemaInfo,
    )

# Đảm bảo in tiếng Việt có dấu không bị lỗi UnicodeEncodeError trên Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Đảm bảo đường dẫn gốc được nhận diện khi chạy trực tiếp
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Đảm bảo môi trường thực thi 100% Offline cục bộ cho HuggingFace & Transformers
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import requests
import streamlit as st

# Cho phép chạy trực tiếp bằng lệnh `python app.py` hoặc nút Run trong VS Code
if __name__ == "__main__":
    if not st.runtime.exists():
        from streamlit.web import cli as stcli
        sys.argv = ["streamlit", "run", __file__]
        sys.exit(stcli.main())

# Chỉ nạp lại các module lõi nếu được kích hoạt tường minh qua biến môi trường (mặc định tắt)
if os.environ.get("CHATBOX_DEV_RELOAD", "0") == "1":
    import importlib
    for _mod in [
        "src.data.batch_ingestion",
        "src.chat.engine",
        "src.retriever.bge_chroma",
        "src.resource.manager",
        "src.data.loader",
    ]:
        if _mod in sys.modules:
            try:
                importlib.reload(sys.modules[_mod])
            except Exception:
                pass

from config.settings import settings
from src.core.models import ChatResponse
from src.auth.service import AuthService
from src.data.conversation_repository import ConversationRepository
from src.data.user_repository import User, UserRepository
from src.ui.auth_views import render_auth_page
from src.ui.theme import CUSTOM_CSS, get_custom_css

# Khởi tạo các repository và service hệ thống thiết yếu cho xác thực
auth_service = AuthService()
conv_repo = ConversationRepository()

logger = logging.getLogger(__name__)

# Đường dẫn Avatar từ assets/
user_img_path = project_root / "assets" / "user.png"
bot_img_path = project_root / "assets" / "bot.png"

USER_AVATAR = str(user_img_path) if user_img_path.exists() else "👤"
BOT_AVATAR = str(bot_img_path) if bot_img_path.exists() else "🤖"


def _get_user_avatar_html() -> str:
    """Tái sử dụng icon người dùng có sẵn trong dự án (assets/user.png) chuẩn kích thước 32x32 px."""
    if user_img_path.exists():
        encoded = base64.b64encode(user_img_path.read_bytes()).decode("utf-8")
        return (
            f'<img src="data:image/png;base64,{encoded}" '
            f'width="32" height="32" '
            f'style="width: 32px !important; height: 32px !important; max-width: 32px !important; max-height: 32px !important; object-fit: contain; display: inline-block;" '
            f'class="user-turn-avatar" alt="User" />'
        )
    return f'<span class="user-turn-avatar" style="font-size: 32px; line-height: 32px; display: inline-block;">{USER_AVATAR}</span>'


USER_AVATAR_HTML = _get_user_avatar_html()

# Cấu hình trang Streamlit chuẩn Web Chatbox Desktop-style
st.set_page_config(
    page_title="Chatbox 2.0 - Tra Cứu Từ Vựng Tiếng Anh",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Áp dụng CSS Theme thích ứng tự động với theme thiết bị (System) / Light / Dark
active_theme_type = getattr(getattr(st, "context", None), "theme", {}).get("type", None)
st.markdown(get_custom_css(active_theme_type), unsafe_allow_html=True)




# --- CÁC HÀM XÁC MINH & CHẨN ĐOÁN RUNTIME (CACHED AN TOÀN) ---

@st.cache_data
def get_hardware_runtime_info() -> Dict[str, Any]:
    """Kiểm tra cấu hình phần cứng một lần, an toàn khi không có GPU hoặc lỗi Torch."""
    try:
        import torch
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            cuda_ver = getattr(torch.version, "cuda", "N/A")
            return {
                "available": True,
                "device_type": "GPU (CUDA)",
                "device_name": device_name,
                "cuda_version": cuda_ver,
                "device_count": torch.cuda.device_count(),
            }
    except Exception as exc:
        logger.warning("Không thể truy vấn thông tin GPU qua Torch: %s", exc)

    return {
        "available": False,
        "device_type": "CPU",
        "device_name": "CPU (CUDA không khả dụng)",
        "cuda_version": "N/A",
        "device_count": 0,
    }


@st.cache_data(ttl=30)
def get_ollama_runtime_status(base_url: str, configured_model: str) -> Dict[str, Any]:
    """Kiểm tra dịch vụ Ollama qua HTTP (cache 30s để tránh spam mạng khi rerun):
    - Phân biệt model cấu hình, model đã cài và model đang nạp.
    """
    clean_url = (base_url or "http://localhost:11434").rstrip("/")
    status: Dict[str, Any] = {
        "online": False,
        "configured_model": configured_model,
        "installed_models": [],
        "running_models": [],
        "error": None,
    }

    try:
        tags_resp = requests.get(f"{clean_url}/api/tags", timeout=1.5)
        if tags_resp.status_code == 200:
            status["online"] = True
            tags_data = tags_resp.json()
            models_list = tags_data.get("models", [])
            status["installed_models"] = [m.get("name") for m in models_list if m.get("name")]

            try:
                ps_resp = requests.get(f"{clean_url}/api/ps", timeout=1.5)
                if ps_resp.status_code == 200:
                    ps_data = ps_resp.json()
                    status["running_models"] = [m.get("name") for m in ps_data.get("models", []) if m.get("name")]
            except Exception:
                pass
        else:
            status["error"] = f"Mã HTTP {tags_resp.status_code}"
    except Exception as exc:
        status["error"] = str(exc)

    return status


def inspect_storage_metrics(engine: Any) -> Dict[str, Any]:
    """Đọc độc lập số lượng bản ghi thực tế của từng tầng lưu trữ."""
    results: Dict[str, Any] = {
        "jsonl_disk_count": None,
        "jsonl_disk_error": None,
        "engine_records_count": None,
        "engine_records_error": None,
        "chroma_count": None,
        "chroma_error": None,
        "bm25_count": None,
        "bm25_error": None,
    }

    # 1. Đọc tệp JSONL trên đĩa (settings.PROCESSED_JSONL_PATH)
    try:
        jsonl_path = settings.PROCESSED_JSONL_PATH
        if jsonl_path.exists():
            with open(jsonl_path, "r", encoding="utf-8") as f:
                lines = sum(1 for line in f if line.strip())
            results["jsonl_disk_count"] = lines
        else:
            results["jsonl_disk_error"] = f"Tệp không tồn tại ({jsonl_path.name})"
    except Exception as exc:
        results["jsonl_disk_error"] = str(exc)

    # 2. Đọc bản ghi trong bộ nhớ ChatEngine
    try:
        if hasattr(engine, "records") and isinstance(engine.records, list):
            results["engine_records_count"] = len(engine.records)
        else:
            results["engine_records_error"] = "engine.records không hợp lệ"
    except Exception as exc:
        results["engine_records_error"] = str(exc)

    # 3. Đọc số vector ChromaDB
    try:
        if hasattr(engine, "bge_retriever") and engine.bge_retriever:
            results["chroma_count"] = engine.bge_retriever.get_collection_count()
        else:
            import chromadb
            client = chromadb.PersistentClient(path=str(settings.CHROMA_DIR))
            coll = client.get_or_create_collection(name=settings.CHROMA_COLLECTION_NAME)
            results["chroma_count"] = coll.count()
    except Exception as exc:
        results["chroma_error"] = str(exc)

    # 4. Đọc số bản ghi BM25
    try:
        if hasattr(engine, "bm25_retriever") and engine.bm25_retriever:
            if hasattr(engine.bm25_retriever, "records") and isinstance(engine.bm25_retriever.records, list):
                results["bm25_count"] = len(engine.bm25_retriever.records)
            else:
                results["bm25_error"] = "bm25_retriever.records không hợp lệ"
        else:
            results["bm25_error"] = "Không tìm thấy bm25_retriever"
    except Exception as exc:
        results["bm25_error"] = str(exc)

    return results


# --- ĐIỀU PHỐI KHỞI TẠO NỀN (BACKGROUND WARM-UP) & SINGLETON CHAT ENGINE ---

import threading

_warmup_started = False
_warmup_lock = threading.Lock()


def start_background_warmup() -> None:
    """Khởi động tác vụ warm-up nền một lần duy nhất trong lúc màn hình đăng nhập hiển thị."""
    global _warmup_started
    with _warmup_lock:
        if _warmup_started:
            return
        _warmup_started = True

    def _worker():
        try:
            from src.chat.engine import start_engine_warmup
            start_engine_warmup()
        except Exception as exc:
            perf_logger.error("[PERF] Lỗi trong launcher warm-up nền: %s", exc)

    worker = threading.Thread(target=_worker, name="chatbox-bg-warmup-launcher", daemon=True)
    worker.start()


def get_engine_state() -> Tuple[str, Optional[str]]:
    """Đọc trạng thái hiện tại của ChatEngine từ luồng Streamlit."""
    if "src.chat.engine" not in sys.modules:
        return "NOT_STARTED", None
    from src.chat.engine import get_engine_state as _engine_state
    return _engine_state()


def is_engine_ready() -> bool:
    """Kiểm tra ChatEngine đã hoàn tất khởi tạo và sẵn sàng phục vụ chưa."""
    state, _ = get_engine_state()
    return state == "READY"


@st.cache_resource(show_spinner=False)
def get_chatbot_engine() -> Any:
    """Lấy singleton instance dùng chung của ChatEngine qua st.cache_resource."""
    from src.chat.engine import get_shared_chat_engine
    return get_shared_chat_engine()


@st.cache_resource(show_spinner=False)
def get_batch_manager() -> Any:
    """Singleton instance của BatchIngestionManager, nạp trễ khi cần."""
    from src.data.batch_ingestion import BatchIngestionManager
    return BatchIngestionManager()


# --- KHỞI TẠO SESSION STATE CỐT LÕI & XÁC THỰC ---
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None
if "current_conversation_id" not in st.session_state:
    st.session_state.current_conversation_id = None
if "tracker" not in st.session_state:
    st.session_state.tracker = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "audit_logs" not in st.session_state:
    st.session_state.audit_logs = []
if "dev_mode" not in st.session_state:
    st.session_state.dev_mode = False
if "status" not in st.session_state:
    st.session_state.status = "Sẵn sàng!"
if "batch_report" not in st.session_state:
    st.session_state.batch_report = None
if "nav_page" not in st.session_state:
    st.session_state.nav_page = "💬 Tra cứu từ vựng"
if "uploader_generation" not in st.session_state:
    st.session_state.uploader_generation = 0
if "is_ingesting" not in st.session_state:
    st.session_state.is_ingesting = False
if "sqlite_configs" not in st.session_state:
    st.session_state.sqlite_configs = {}
if "show_clear_kb_confirm" not in st.session_state:
    st.session_state.show_clear_kb_confirm = False
if "is_processing" not in st.session_state:
    st.session_state.is_processing = False

# Xác minh trạng thái phiên làm việc ở backend mỗi lần rerun
if st.session_state.auth_user is not None:
    verified_user = auth_service.verify_active_session(st.session_state.auth_user.id)
    if not verified_user:
        st.session_state.auth_user = None
        st.session_state.messages = []
        st.session_state.current_conversation_id = None
        st.warning("⚠️ Phiên làm việc đã hết hạn hoặc tài khoản đã bị vô hiệu hóa.")
        st.rerun()
    else:
        st.session_state.auth_user = verified_user

current_user: Optional[User] = st.session_state.auth_user
if current_user is None and not st.runtime.exists():
    # Khi chạy import từ unit tests ngoài runtime của Streamlit
    current_user = User(
        id="test_bare_mode_user",
        username="test_user",
        password_hash="mock",
        display_name="Test User",
        role="user",
        is_active=True,
        created_at="2026-01-01 00:00:00",
        last_login_at=None,
        updated_at="2026-01-01 00:00:00",
    )

# CỔNG BẢO VỆ XÁC THỰC: NẾU CHƯA ĐĂNG NHẬP, DỰNG FORM ĐĂNG NHẬP TRƯỚC RỒI MỚI KHỞI CHẠY WARM-UP NỀN
if current_user is None and st.runtime.exists():
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="stExpandSidebarButton"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True
    )
    # 1. Dựng màn hình đăng nhập trước
    render_auth_page(auth_service, conv_repo)
    perf_logger.info("[PERF] Màn hình đăng nhập sẵn sàng sau %.3f giây.", time.perf_counter() - _T_APP_START)
    # 2. Khởi chạy warm-up nền sau khi form đã được render (cùng tiến trình, an toàn, idempotent)
    start_background_warmup()
    st.stop()

# KHỞI TẠO CÁC THÀNH PHẦN NẶNG CHỈ KHI NGƯỜI DÙNG ĐÃ XÁC THỰC THÀNH CÔNG
_t_login_ready_start = time.perf_counter()
engine_state, engine_error = get_engine_state()
engine = None
engine_is_ready = False

if engine_state == "READY":
    engine = get_chatbot_engine()
    engine_is_ready = True
elif engine_state == "ERROR":
    st.error(f"❌ Không thể khởi tạo động cơ AI: {engine_error}. Vui lòng thử lại hoặc liên hệ Quản trị viên.")
else:
    # WARMING_UP hoặc NOT_STARTED
    if engine_state == "NOT_STARTED":
        # Khởi tạo an toàn (cho trường hợp mock test session trực tiếp hoặc direct script)
        try:
            engine = get_chatbot_engine()
            engine_is_ready = True
        except Exception as exc:
            st.error(f"❌ Không thể khởi tạo động cơ AI: {exc}")
    else:
        # Đang warm-up nền: nếu người dùng đang ở trang chat, chờ tối đa 0.2s để bắt kịp nếu warm-up vừa xong
        if st.session_state.nav_page == "💬 Tra cứu từ vựng":
            try:
                from src.chat.engine import get_shared_chat_engine
                engine = get_shared_chat_engine(timeout=0.2)
                engine_is_ready = True
            except TimeoutError:
                engine_is_ready = False
                engine = None
            except Exception as exc:
                engine_is_ready = False
                engine = None
                st.error(f"❌ Không thể khởi tạo động cơ AI: {exc}")

if engine_is_ready:
    perf_logger.info("[PERF] Giao diện Chat & Engine sẵn sàng sau %.3f giây từ khi xác thực.", time.perf_counter() - _t_login_ready_start)

# Khởi tạo TopicTracker riêng cho từng phiên / người dùng (cô lập session, không gán đè toàn cục)
if st.session_state.tracker is None:
    from src.chat.topic_tracker import TopicTracker
    tracker_records = engine.records if (engine is not None and hasattr(engine, "records")) else []
    st.session_state.tracker = TopicTracker(records=tracker_records)
elif engine is not None and hasattr(engine, "records") and not st.session_state.tracker.vocab_words:
    st.session_state.tracker.load_known_words(engine.records)

# Logo hiển thị cạnh nút thu gọn sidebar chuẩn ChatGPT
st.logo(str(bot_img_path), icon_image=str(bot_img_path))
kb_records_count = len(engine.records) if (engine is not None and hasattr(engine, "records") and engine.records) else 7053


def get_conversation_time_group(iso_timestamp: Optional[str]) -> str:
    """Phân nhóm cuộc trò chuyện theo thời gian: Hôm nay, 7 ngày gần đây, Trước đó."""
    if not iso_timestamp:
        return "Trước đó"
    try:
        ts_clean = str(iso_timestamp).replace("T", " ").split(".")[0]
        dt = datetime.strptime(ts_clean, "%Y-%m-%d %H:%M:%S")
        diff_days = (date.today() - dt.date()).days
        if diff_days <= 0:
            return "Hôm nay"
        elif diff_days <= 7:
            return "7 ngày gần đây"
        else:
            return "Trước đó"
    except Exception:
        return "Trước đó"


# ==============================================================================
# CÁC HÀM RENDER & XỬ LÝ HỘI THOẠI CHUẨN MODERN STREAMLIT CHAT UI
# ==============================================================================

def render_user_turn(content: str) -> None:
    """Hiển thị lượt tin nhắn của người dùng: căn phải với bong bóng tối bo tròn phong cách ChatGPT."""
    with st.chat_message("user", avatar=USER_AVATAR):
        col_spacer, col_user = st.columns([1, 4])
        with col_user:
            st.markdown(
                f"""
                <div class="user-turn-wrapper">
                    <div class="user-turn-author">{USER_AVATAR_HTML}</div>
                    <div class="user-turn-body">{html.escape(content)}</div>
                </div>
                """,
                unsafe_allow_html=True
            )


def _format_source_badge_html(source_val: Optional[str], sheet_val: Optional[str] = None) -> str:
    """Định dạng badge nguồn dữ liệu: nếu là URL (ví dụ link từ điển Cambridge/Oxford trong file Excel)
    thì hiển thị hyperlink nhấp mở tab mới kèm icon; nếu là tên file thì hiển thị tên chuẩn kèm Sheet (nếu có)."""
    if not source_val:
        return ""
    str_src = str(source_val).strip()
    is_url = str_src.startswith("http://") or str_src.startswith("https://")
    badges = []
    if is_url:
        label = "Cambridge Dictionary" if "cambridge" in str_src.lower() else ("Oxford Learner's" if "oxford" in str_src.lower() else str_src)
        badges.append(
            f'<span class="source-badge source-badge-primary">📚 Nguồn: <a href="{html.escape(str_src)}" target="_blank" rel="noopener noreferrer" style="color: inherit; text-decoration: underline; font-weight: bold;">{html.escape(label)} ↗</a></span>'
        )
    else:
        badges.append(f'<span class="source-badge source-badge-primary">📚 Nguồn: <b>{html.escape(str_src)}</b></span>')

    if sheet_val:
        badges.append(f'<span class="source-badge">📑 Sheet: <b>{html.escape(str(sheet_val))}</b></span>')

    return "".join(badges)


def render_provenance_and_inspector(meta: Optional[ChatResponse]) -> None:
    """Hiển thị thông tin xuất xứ dữ liệu (Provenance) và bảng kỹ thuật (Inspector) tinh tế."""
    if meta is None:
        return

    source_file = getattr(meta, "source", None)
    rec_id = getattr(meta, "record_id", None)
    word_val = getattr(meta, "word", None)
    sheet_val = getattr(meta, "sheet", None)

    if getattr(meta, "candidates", None) and len(meta.candidates) > 0:
        top_candidate = meta.candidates[0].record
        if not source_file:
            source_file = getattr(top_candidate, "source", None) or getattr(top_candidate, "source_file", None)
        if not rec_id:
            rec_id = getattr(top_candidate, "record_id", None) or getattr(top_candidate, "id", None)
        if not word_val:
            word_val = getattr(top_candidate, "word", None)
        if not sheet_val:
            sheet_val = getattr(top_candidate, "sheet", None)

    has_provenance = any([rec_id, source_file, word_val, sheet_val])
    if has_provenance:
        with st.expander("📄 Nguồn dữ liệu · Mở rộng", expanded=False):
            prov_html = []
            if source_file:
                str_src = str(source_file).strip()
                if str_src.startswith("http://") or str_src.startswith("https://"):
                    label = "Cambridge Dictionary" if "cambridge" in str_src.lower() else ("Oxford Learner's" if "oxford" in str_src.lower() else str_src)
                    prov_html.append(f'<span class="source-badge source-badge-primary">📚 Nguồn: <a href="{html.escape(str_src)}" target="_blank" rel="noopener noreferrer" style="color: inherit; text-decoration: underline; font-weight: bold;">{html.escape(label)} ↗</a></span>')
                else:
                    prov_html.append(f'<span class="source-badge source-badge-primary">📚 Nguồn: <b>{html.escape(str_src)}</b></span>')
            if word_val:
                prov_html.append(f'<span class="source-badge">📖 Từ: <b>{html.escape(str(word_val))}</b></span>')
            if rec_id:
                prov_html.append(f'<span class="source-badge source-badge-secondary">🏷️ Mã: <b>{html.escape(str(rec_id))}</b></span>')
            if sheet_val:
                prov_html.append(f'<span class="source-badge">📑 Sheet: <b>{html.escape(str(sheet_val))}</b></span>')
            st.markdown("".join(prov_html), unsafe_allow_html=True)

    if st.session_state.get("dev_mode", False):
        with st.expander("🔬 Bảng phân tích kỹ thuật (Inspector)", expanded=False):
            ic1, ic2, ic3, ic4 = st.columns(4)
            ic1.metric("Response Mode", str(getattr(meta, "mode", "N/A")))
            ic2.metric("PhoBERT Intent", str(getattr(meta, "intent", "N/A") or "N/A"))
            ic3.metric("RRF Score", f"{getattr(meta, 'rrf_score', 0.0):.4f}")
            ic4.metric("Độ trễ", f"{getattr(meta, 'latency_ms', 0.0):.1f} ms")


def render_assistant_turn(content: str, meta: Optional[ChatResponse] = None) -> None:
    """Hiển thị lượt tin nhắn chatbot theo phong cách ChatGPT tinh gọn."""
    with st.chat_message("assistant", avatar=BOT_AVATAR):
        st.markdown(content)
        # Hiển thị trực tiếp nguồn dữ liệu cạnh câu trả lời
        source_name = getattr(meta, "source", None) if meta else None
        sheet_name = getattr(meta, "sheet", None) if meta else None
        if meta and getattr(meta, "candidates", None) and len(meta.candidates) > 0:
            top_rec = meta.candidates[0].record
            if not source_name:
                source_name = getattr(top_rec, "source", None)
            if not sheet_name:
                sheet_name = getattr(top_rec, "sheet", None)
        if source_name:
            badge_html = _format_source_badge_html(source_name, sheet_name)
            if badge_html:
                st.markdown(
                    f'<div style="margin-top: 4px; margin-bottom: 6px;">{badge_html}</div>',
                    unsafe_allow_html=True
                )
        render_provenance_and_inspector(meta)


def process_user_query(
    clean_input: str,
    chat_engine: Any,
    current_user: Optional[User] = None,
    conv_repo: Optional[ConversationRepository] = None,
    messages_container=None,
    empty_state_placeholder=None,
) -> Optional[ChatResponse]:
    """Quy trình xử lý một câu hỏi của người dùng chuẩn luồng hiện đại:
    1. Cập nhật câu hỏi vào st.session_state.messages và lưu bền vững vào SQLite.
    2. Render bubble người dùng ngay lập tức trên UI trước khi bắt đầu backend.
    3. Render bubble assistant cùng placeholder trạng thái 'Đang phân tích câu hỏi & tìm kiếm dữ liệu...'.
    4. Gọi ChatEngine.ask_stream() để sinh câu trả lời theo luồng (streaming).
    5. Cập nhật các chunk phản hồi thay thế placeholder trạng thái.
    6. Lưu câu trả lời hoàn chỉnh cùng metadata vào st.session_state.messages và SQLite.
    7. Ghi nhận nhật ký kiểm toán (audit log).
    """
    if not clean_input:
        return None

    if current_user is None:
        current_user = st.session_state.get("auth_user")

    t_query_start = time.perf_counter()

    # Đảm bảo cuộc hội thoại tồn tại trong cơ sở dữ liệu nếu có user và conv_repo
    conv_id = st.session_state.get("current_conversation_id")
    if current_user and conv_repo:
        if not conv_id:
            short_title = clean_input[:35] + ("..." if len(clean_input) > 35 else "")
            try:
                new_conv = conv_repo.create_conversation(current_user.id, short_title)
                conv_id = new_conv.id
                st.session_state.current_conversation_id = conv_id
            except Exception as e_c:
                logger.error("Lỗi tạo conversation: %s", e_c)

        if conv_id:
            try:
                conv_repo.add_message(current_user.id, conv_id, "user", clean_input)
            except Exception as save_u_err:
                logger.error("Lỗi khi lưu tin nhắn người dùng: %s", save_u_err)

    st.session_state.is_processing = True
    try:
        # Bước 1: Lưu câu hỏi người dùng vào lịch sử ngay
        st.session_state.messages.append({
            "role": "user",
            "content": clean_input
        })
        st.session_state.status = "Đang xử lý..."

        # Bước 2: Xóa empty state nếu có
        if empty_state_placeholder is not None:
            empty_state_placeholder.empty()

        # Bước 3: Render trong container tin nhắn
        render_ctx = messages_container if messages_container is not None else st.container()
        with render_ctx:
            # 3A. Hiện bubble user ngay
            render_user_turn(clean_input)

            # 3B. Hiện bubble assistant với placeholder trạng thái đang xử lý
            with st.chat_message("assistant", avatar=BOT_AVATAR):
                status_placeholder = st.empty()
                status_placeholder.markdown(
                    '<div class="bot-status-indicator">'
                    '<span class="status-spinner">⏳</span> '
                    '<span>Đang phân tích câu hỏi & tìm kiếm dữ liệu...</span>'
                    '</div>',
                    unsafe_allow_html=True
                )

                response_holder: Dict[str, Any] = {"meta": None}

                def stream_adapter():
                    first_chunk = True
                    try:
                        # Truyền tracker riêng của session để bảo đảm cô lập hoàn toàn giữa các phiên
                        session_tracker = st.session_state.get("tracker", None)
                        try:
                            stream_iter = chat_engine.ask_stream(clean_input, tracker=session_tracker)
                        except TypeError:
                            stream_iter = chat_engine.ask_stream(clean_input)

                        for token, meta in stream_iter:
                            if meta is not None:
                                response_holder["meta"] = meta
                            if token:
                                if first_chunk:
                                    status_placeholder.empty()
                                    first_chunk = False
                                    perf_logger.info(
                                        "[PERF] Thời gian từ câu hỏi đầu đến phản hồi đầu tiên (TTFT): %.3f giây.",
                                        time.perf_counter() - t_query_start
                                    )
                                yield token
                    finally:
                        if first_chunk:
                            status_placeholder.empty()

                try:
                    stream_gen = stream_adapter()
                    full_answer = st.write_stream(stream_gen)
                    status_placeholder.empty()
                except Exception as ask_err:
                    status_placeholder.empty()
                    logger.error("Lỗi khi xử lý truy vấn: %s", ask_err, exc_info=True)
                    error_answer = (
                        f"⚠️ **Không thể kết nối hoặc xử lý câu trả lời từ mô hình.**\n\n"
                        f"- Chi tiết lỗi: `{ask_err}`\n"
                        f"- Vui lòng kiểm tra dịch vụ Ollama cục bộ ({settings.OLLAMA_BASE_URL}) hoặc thử lại sau."
                    )
                    st.markdown(error_answer)
                    full_answer = error_answer
                    response_holder["meta"] = ChatResponse(
                        answer=error_answer,
                        mode="ERROR",
                        latency_ms=0.0
                    )

                final_meta: Optional[ChatResponse] = response_holder.get("meta")
                persisted_answer = final_meta.answer if (final_meta and final_meta.answer) else full_answer

                # Hiển thị trực tiếp nguồn dữ liệu cạnh câu trả lời
                source_name = getattr(final_meta, "source", None) if final_meta else None
                sheet_name = getattr(final_meta, "sheet", None) if final_meta else None
                if final_meta and getattr(final_meta, "candidates", None) and len(final_meta.candidates) > 0:
                    top_rec = final_meta.candidates[0].record
                    if not source_name:
                        source_name = getattr(top_rec, "source", None)
                    if not sheet_name:
                        sheet_name = getattr(top_rec, "sheet", None)
                if source_name:
                    badge_html = _format_source_badge_html(source_name, sheet_name)
                    if badge_html:
                        st.markdown(
                            f'<div style="margin-top: 4px; margin-bottom: 6px;">{badge_html}</div>',
                            unsafe_allow_html=True
                        )

                # Render nguồn dữ liệu và inspector
                render_provenance_and_inspector(final_meta)

        # Bước 4: Lưu câu trả lời hoàn chỉnh vào session state
        st.session_state.messages.append({
            "role": "assistant",
            "content": persisted_answer,
            "meta": final_meta
        })
        st.session_state.status = "Hoàn tất!"

        # Bước 5: Lưu câu trả lời vào SQLite bền vững
        meta_json_str = None
        if final_meta:
            try:
                meta_json_str = json.dumps({
                    "mode": getattr(final_meta, "mode", None),
                    "intent": getattr(final_meta, "intent", None),
                    "record_id": getattr(final_meta, "record_id", None),
                    "rrf_score": getattr(final_meta, "rrf_score", 0.0),
                    "latency_ms": getattr(final_meta, "latency_ms", 0.0),
                    "word": getattr(final_meta, "word", None),
                    "source": getattr(final_meta, "source", None),
                    "sheet": getattr(final_meta, "sheet", None),
                }, ensure_ascii=False)
            except Exception:
                pass

        if current_user and conv_repo and conv_id:
            try:
                conv_repo.add_message(current_user.id, conv_id, "assistant", persisted_answer, meta_json_str)
                # Tự động cập nhật tiêu đề nếu vẫn là 'Cuộc trò chuyện mới'
                curr_c = conv_repo.get_conversation(current_user.id, conv_id)
                if curr_c and curr_c.title == "Cuộc trò chuyện mới":
                    auto_title = clean_input[:35] + ("..." if len(clean_input) > 35 else "")
                    conv_repo.update_title(current_user.id, conv_id, auto_title)
            except Exception as save_bot_err:
                logger.error("Lỗi khi lưu tin nhắn chatbot: %s", save_bot_err)

        # Bước 6: Ghi audit log phiên
        active_word_val = getattr(chat_engine.tracker, "active_word", None) if hasattr(chat_engine, "tracker") else None
        st.session_state.audit_logs.append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "query": clean_input,
            "mode": str(getattr(final_meta, "mode", "UNKNOWN")),
            "intent": getattr(final_meta, "intent", None),
            "active_word": active_word_val,
            "record_id": getattr(final_meta, "record_id", None),
            "rrf_score": getattr(final_meta, "rrf_score", 0.0),
            "latency_ms": getattr(final_meta, "latency_ms", 0.0),
            "answer": persisted_answer
        })

        return final_meta

    finally:
        st.session_state.is_processing = False


# ==============================================================================
# SIDEBAR BÊN TRÁI: BỐ CỤC CHATGPT (3 ZONE: TOP, SCROLLABLE HISTORY, PINNED ACCOUNT)
# ==============================================================================
with st.sidebar:
    # 1. ZONE TOP (Header & New Chat)
    with st.container(key="sidebar_top"):
        st.markdown(
            """
            <div class="sidebar-header-box">
                <span class="sidebar-app-icon">🤖</span>
                <div class="sidebar-brand-text">
                    <span class="sidebar-app-title">Chatbox 2.0</span>
                    <span class="sidebar-app-badge">Local</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if st.button("➕ Đoạn chat mới", key="btn_sidebar_new_chat", use_container_width=True, help="Tạo cuộc hội thoại mới"):
            st.session_state.current_conversation_id = None
            st.session_state.messages = []
            if st.session_state.tracker:
                st.session_state.tracker.clear()
            if hasattr(engine, "tracker") and hasattr(engine.tracker, "clear"):
                engine.tracker.clear()
            st.session_state.status = "Sẵn sàng!"
            st.session_state.is_processing = False
            st.session_state.nav_page = "💬 Tra cứu từ vựng"
            st.toast("Đã chuyển sang cuộc trò chuyện mới.", icon="✨")
            st.rerun()

        search_query = st.text_input(
            "Tìm kiếm cuộc trò chuyện...",
            placeholder="🔍 Tìm đoạn chat...",
            key="sidebar_search_conv",
            label_visibility="collapsed"
        ).strip().lower()

    # 2. ZONE HISTORY (Cuộn độc lập ở giữa)
    with st.container(key="sidebar_history"):
        user_convs = conv_repo.list_conversations(current_user.id, limit=50)
        valid_convs = [c for c in user_convs if c.message_count > 0 or c.id == st.session_state.current_conversation_id]
        if search_query:
            filtered_convs = [c for c in valid_convs if search_query in c.title.lower()]
        else:
            filtered_convs = valid_convs

        # Phân tách nhóm hội thoại đã ghim và chưa ghim
        pinned_convs = [c for c in filtered_convs if getattr(c, "is_pinned", False)]
        unpinned_convs = [c for c in filtered_convs if not getattr(c, "is_pinned", False)]

        grouped_convs: Dict[str, List[Any]] = {
            "Hôm nay": [],
            "7 ngày gần đây": [],
            "Trước đó": []
        }
        for c in unpinned_convs:
            grp = get_conversation_time_group(getattr(c, "updated_at", None) or getattr(c, "created_at", None))
            grouped_convs[grp].append(c)

        has_convs = len(pinned_convs) > 0 or any(len(items) > 0 for items in grouped_convs.values())

        def _render_conv_item(conv_item):
            is_active_conv = (conv_item.id == st.session_state.current_conversation_id)
            display_title = conv_item.title if len(conv_item.title) <= 18 else conv_item.title[:16] + "..."
            btn_key = f"btn_conv_active_{conv_item.id}" if is_active_conv else f"btn_conv_{conv_item.id}"
            btn_icon = "💬 " if not is_active_conv else "👉 "

            col_btn, col_pin, col_del = st.columns([0.72, 0.14, 0.14])
            with col_btn:
                if st.button(f"{btn_icon}{display_title}", key=btn_key, use_container_width=True, help=conv_item.title):
                    if not is_active_conv:
                        st.session_state.current_conversation_id = conv_item.id
                        db_msgs = conv_repo.get_messages(current_user.id, conv_item.id)
                        st.session_state.messages = []
                        for m in db_msgs:
                            meta_obj = None
                            if m.meta_json:
                                try:
                                    md = json.loads(m.meta_json)
                                    meta_obj = ChatResponse(
                                        answer=m.content,
                                        mode=md.get("mode", "UNKNOWN"),
                                        intent=md.get("intent"),
                                        record_id=md.get("record_id"),
                                        rrf_score=md.get("rrf_score", 0.0),
                                        latency_ms=md.get("latency_ms", 0.0),
                                        word=md.get("word"),
                                        source=md.get("source"),
                                        sheet=md.get("sheet"),
                                    )
                                except Exception:
                                    pass
                            st.session_state.messages.append({
                                "role": m.role,
                                "content": m.content,
                                "meta": meta_obj
                            })
                        if st.session_state.tracker:
                            st.session_state.tracker.clear()
                        engine.tracker.clear()
                        st.session_state.nav_page = "💬 Tra cứu từ vựng"
                        st.rerun()

            with col_pin:
                pin_icon = "📍" if getattr(conv_item, "is_pinned", False) else "📌"
                pin_help = "Bỏ ghim" if getattr(conv_item, "is_pinned", False) else "Ghim hội thoại"
                if st.button(pin_icon, key=f"btn_pin_{conv_item.id}", help=pin_help):
                    conv_repo.toggle_pin_conversation(current_user.id, conv_item.id)
                    st.rerun()

            with col_del:
                if st.button("🗑️", key=f"btn_del_{conv_item.id}", help="Xóa cuộc trò chuyện"):
                    conv_repo.delete_conversation(current_user.id, conv_item.id)
                    if st.session_state.current_conversation_id == conv_item.id:
                        st.session_state.current_conversation_id = None
                        st.session_state.messages = []
                    st.toast("Đã xóa cuộc trò chuyện.", icon="🗑️")
                    st.rerun()

        if has_convs:
            if pinned_convs:
                st.markdown('<div class="history-time-heading">📌 ĐÃ GHIM</div>', unsafe_allow_html=True)
                for c in pinned_convs:
                    _render_conv_item(c)

            for grp_name in ["Hôm nay", "7 ngày gần đây", "Trước đó"]:
                items = grouped_convs[grp_name]
                if not items:
                    continue
                st.markdown(f'<div class="history-time-heading">{grp_name}</div>', unsafe_allow_html=True)
                for c in items:
                    _render_conv_item(c)
        else:
            st.caption("Không tìm thấy đoạn chat nào." if search_query else "Chưa có đoạn chat nào.")

    # 3. ZONE FOOTER (Tài khoản & Cài đặt ghim cố định ở góc dưới cùng bên trái)
    with st.container(key="sidebar_footer"):
        role_badge_class = "role-badge-admin" if current_user.role == "admin" else "role-badge-user"
        role_name_text = "Quản trị viên" if current_user.role == "admin" else "Người dùng"

        with st.popover(f"👤 {current_user.display_name}", use_container_width=True):
            st.markdown(
                f"""
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                    <div>{USER_AVATAR_HTML}</div>
                    <div>
                        <div style="font-weight: 600; color: var(--text-primary); font-size: 0.95rem;">{html.escape(current_user.display_name)}</div>
                        <div style="color: var(--text-muted); font-size: 0.8rem;">@{html.escape(current_user.username)} · <span class="{role_badge_class}">{role_name_text}</span></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.markdown("---")
            st.markdown("**Điều hướng:**")
            if st.button("💬 Trò chuyện", key="nav_popover_chat", use_container_width=True):
                st.session_state.nav_page = "💬 Tra cứu từ vựng"
                st.rerun()
            if st.button("👤 Hồ sơ cá nhân", key="nav_popover_profile", use_container_width=True):
                st.session_state.nav_page = "👤 Thông tin cá nhân"
                st.rerun()

            if current_user.role == "admin":
                st.markdown("---")
                st.markdown("**Quản trị hệ thống:**")
                if st.button("👥 Quản lý tài khoản", key="nav_popover_admin_users", use_container_width=True):
                    st.session_state.nav_page = "👥 Quản lý tài khoản"
                    st.rerun()
                if st.button("🗄️ Quản lý dữ liệu", key="nav_popover_admin_kb", use_container_width=True):
                    st.session_state.nav_page = "🗄️ Quản lý dữ liệu"
                    st.rerun()
                if st.button("📈 Chẩn đoán & Nhật ký", key="nav_popover_admin_diag", use_container_width=True):
                    st.session_state.nav_page = "📈 Chẩn đoán & Nhật ký"
                    st.rerun()

            st.markdown("---")
            st.markdown("**Cài đặt:**")
            dev_toggle = st.toggle("🔬 Bảng phân tích kỹ thuật (Inspector)", value=st.session_state.get("dev_mode", False), key="toggle_inspector_popover")
            if dev_toggle != st.session_state.get("dev_mode", False):
                st.session_state.dev_mode = dev_toggle
                st.rerun()

            if st.session_state.current_conversation_id:
                if st.button("🗑️ Xóa đoạn chat hiện tại", key="btn_popover_del_curr", use_container_width=True):
                    conv_repo.delete_conversation(current_user.id, st.session_state.current_conversation_id)
                    st.session_state.current_conversation_id = None
                    st.session_state.messages = []
                    if st.session_state.tracker:
                        st.session_state.tracker.clear()
                    engine.tracker.clear()
                    st.toast("Đã xóa đoạn chat hiện tại.", icon="🗑️")
                    st.rerun()

            if st.button("🧹 Xóa toàn bộ lịch sử", key="btn_popover_clear_all", use_container_width=True):
                deleted_cnt = conv_repo.clear_user_history(current_user.id)
                st.session_state.current_conversation_id = None
                st.session_state.messages = []
                if st.session_state.tracker:
                    st.session_state.tracker.clear()
                engine.tracker.clear()
                st.toast(f"Đã xóa {deleted_cnt} đoạn chat.", icon="🧹")
                st.rerun()

            st.markdown("---")
            if st.button("🚪 Đăng xuất", key="btn_popover_logout", use_container_width=True):
                auth_service.logout(current_user)
                st.session_state.auth_user = None
                st.session_state.messages = []
                st.session_state.current_conversation_id = None
                st.session_state.tracker = None
                if hasattr(engine, "tracker") and hasattr(engine.tracker, "clear"):
                    engine.tracker.clear()
                st.toast("Đã đăng xuất an toàn.", icon="👋")
                st.rerun()



if st.session_state.nav_page == "💬 Tra cứu từ vựng":
    # --------------------------------------------------------------------------
    # TRANG 1: 💬 TRA CỨU TỪ VỰNG (MAIN CHAT VIEW CHUẨN CHATGPT)
    # --------------------------------------------------------------------------

    # 1. Header Khung Chat: Tiêu đề + Badge 'Local AI' + Đổi tên cuộc hội thoại
    curr_conv_info = conv_repo.get_conversation(current_user.id, st.session_state.current_conversation_id) if st.session_state.current_conversation_id else None
    conv_display_title = curr_conv_info.title if curr_conv_info else "Cuộc trò chuyện mới"

    col_h_left, col_h_right = st.columns([4, 1])
    with col_h_left:
        st.markdown(
            f"""
            <div class="chat-top-bar" style="border-bottom: none; margin-bottom: 0; padding-bottom: 0;">
                <div class="chat-top-left">
                    <span class="chat-view-title">{html.escape(conv_display_title)}</span>
                    <span class="chat-local-pill">Local AI</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col_h_right:
        if st.session_state.current_conversation_id:
            with st.popover("✏️ Đổi tên", use_container_width=True):
                new_title_inp = st.text_input(
                    "Tiêu đề mới:",
                    value=conv_display_title,
                    key="rename_conv_input"
                ).strip()
                if st.button("Lưu", key="btn_save_conv_title", use_container_width=True):
                    if new_title_inp:
                        conv_repo.update_title(current_user.id, st.session_state.current_conversation_id, new_title_inp)
                        st.toast("Đã cập nhật tiêu đề.", icon="✏️")
                        st.rerun()

    st.markdown('<div style="border-bottom: 1px solid var(--border-subtle); margin-bottom: 1rem; margin-top: 4px;"></div>', unsafe_allow_html=True)

    if not engine_is_ready:
        st.info("⏳ Động cơ AI đang được chuẩn bị dưới nền. Vui lòng đợi trong giây lát, ô nhập câu hỏi sẽ mở khóa ngay khi sẵn sàng...")

    # 2. Vùng hiển thị tin nhắn (cuộn tự nhiên theo trình duyệt)
    messages_container = st.container()

    with messages_container:
        empty_state_placeholder = st.empty()
        if not st.session_state.messages:
            # Màn hình chào mừng khi chưa có tin nhắn (Empty State chuẩn ChatGPT)
            with empty_state_placeholder.container():
                st.markdown(
                    """
                    <div class="chat-empty-state-box">
                        <div class="chat-empty-icon">🤖</div>
                        <div class="chat-empty-title">Hôm nay bạn muốn học từ vựng nào?</div>
                        <div class="chat-empty-subtitle">Tra cứu nghĩa từ, ví dụ câu, phát âm, thành ngữ hoặc so sánh ngữ pháp tiếng Anh.</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    if st.button("💡 **Hỏi nghĩa từ 'about'**\n\nTra cứu nghĩa, phát âm và ví dụ câu", key="sug_card_1", use_container_width=True, disabled=not engine_is_ready):
                        st.session_state["pending_query"] = "about nghĩa là gì?"
                        st.rerun()
                    if st.button("💡 **Phân biệt 'affect' và 'effect'**\n\nCách dùng chuẩn trong câu và ngữ pháp", key="sug_card_2", use_container_width=True, disabled=not engine_is_ready):
                        st.session_state["pending_query"] = "Phân biệt affect và effect cách dùng và ví dụ"
                        st.rerun()
                with col_s2:
                    if st.button("💡 **Collocations với 'decision'**\n\nCác cụm kết hợp từ tự nhiên hay gặp", key="sug_card_3", use_container_width=True, disabled=not engine_is_ready):
                        st.session_state["pending_query"] = "Cho các collocations thông dụng với từ decision kèm ví dụ"
                        st.rerun()
                    if st.button("💡 **Giải thích từ 'resilient'**\n\nKèm định nghĩa, từ loại và ví dụ", key="sug_card_4", use_container_width=True, disabled=not engine_is_ready):
                        st.session_state["pending_query"] = "resilient nghĩa là gì?"
                        st.rerun()
        else:
            for idx, msg in enumerate(st.session_state.messages):
                role = msg.get("role", "assistant")
                content = msg.get("content", "")
                meta: Optional[ChatResponse] = msg.get("meta")

                if role == "user":
                    render_user_turn(content)
                else:
                    render_assistant_turn(content, meta)

    # Xử lý câu hỏi từ gợi ý (suggestion card) nếu có
    pending_query = st.session_state.pop("pending_query", None)
    if pending_query and not st.session_state.get("is_processing", False):
        process_user_query(
            clean_input=pending_query,
            chat_engine=engine,
            current_user=current_user,
            conv_repo=conv_repo,
            messages_container=messages_container,
            empty_state_placeholder=empty_state_placeholder,
        )
        st.rerun()

    # 3. Ô nhập câu hỏi st.chat_input (nằm ở đáy vùng chính qua API chính thức của Streamlit)
    chat_placeholder = "Hỏi về một từ vựng tiếng Anh hoặc câu hỏi bất kỳ..." if engine_is_ready else "Đang khởi tạo động cơ AI, vui lòng đợi..."
    user_query = st.chat_input(chat_placeholder, disabled=not engine_is_ready)
    if user_query:
        clean_input = user_query.strip()
        if clean_input and not st.session_state.get("is_processing", False):
            process_user_query(
                clean_input=clean_input,
                chat_engine=engine,
                current_user=current_user,
                conv_repo=conv_repo,
                messages_container=messages_container,
                empty_state_placeholder=empty_state_placeholder,
            )


elif st.session_state.nav_page == "👥 Quản lý tài khoản":
    # --------------------------------------------------------------------------
    # TRANG QUẢN LÝ TÀI KHOẢN & NGƯỜI DÙNG (ADMIN ONLY)
    # --------------------------------------------------------------------------
    col_ret_1, col_ret_2 = st.columns([1, 5])
    with col_ret_1:
        if st.button("← Trò chuyện", key="btn_ret_from_admin_users"):
            st.session_state.nav_page = "💬 Tra cứu từ vựng"
            st.rerun()

    try:
        auth_service.require_admin(current_user)
        from src.ui.admin_dashboard import render_admin_dashboard
        render_admin_dashboard(auth_service, conv_repo, current_user)
    except PermissionError as perm_err:
        st.error(f"❌ Truy cập bị từ chối: {perm_err}")


elif st.session_state.nav_page == "🗄️ Quản lý dữ liệu":
    # --------------------------------------------------------------------------
    # TRANG 2: 🗄️ QUẢN LÝ DỮ LIỆU (KNOWLEDGE BASE MANAGEMENT - ADMIN ONLY)
    # --------------------------------------------------------------------------
    col_ret_1, col_ret_2 = st.columns([1, 5])
    with col_ret_1:
        if st.button("← Trò chuyện", key="btn_ret_from_admin_kb"):
            st.session_state.nav_page = "💬 Tra cứu từ vựng"
            st.rerun()

    try:
        auth_service.require_admin(current_user)
    except PermissionError as perm_err:
        st.error(f"❌ Truy cập bị từ chối: Yêu cầu quyền Quản trị viên (Admin) để thao tác trên Knowledge Base.")
        st.stop()

    from src.data.batch_ingestion import BatchStatus, FileStatus
    from src.data.loaders.sqlite_loader import (
        SQLiteLoader,
        SQLiteMappingConfig,
        SQLiteMappingMode,
        SQLiteSchemaInfo,
    )
    batch_manager = get_batch_manager()
    with st.container(border=True):
        st.markdown('<div class="panel-card-header">🗄️ Quản Trị & Cập Nhật Kho Tri Thức</div>', unsafe_allow_html=True)
        st.markdown(
            "Hỗ trợ tải lên cùng lúc nhiều tệp dữ liệu thuộc **các định dạng tài liệu** (PDF, DOCX, XLSX, CSV, JSON, TXT, MD, DB, SQLITE) "
            "để tự động trích xuất, khử trùng lặp và cập nhật cơ sở dữ liệu vector mà không cần khởi động lại ứng dụng."
        )

        # 1. Khung Uploader Đa Tệp
        uploader_key = f"uploader_batch_multi_files_{st.session_state.uploader_generation}"
        uploaded_batch_files = st.file_uploader(
            label="Chọn một hoặc nhiều tệp để nạp vào Knowledge Base:",
            type=["pdf", "docx", "txt", "csv", "xlsx", "json", "jsonl", "md", "db", "sqlite"],
            accept_multiple_files=True,
            help="Hỗ trợ: PDF, Word (.docx), Excel (.xlsx), CSV (.csv), JSON (.json, .jsonl), Text (.txt, .md), SQLite Database (.db, .sqlite).",
            key=uploader_key
        )

        if uploaded_batch_files:
            st.markdown(f"**Danh sách tệp chuẩn bị nạp ({len(uploaded_batch_files)} tệp):**")
            file_preview_data = []
            for uf in uploaded_batch_files:
                file_preview_data.append({
                    "Tên tệp": uf.name,
                    "Kích thước (KB)": round(uf.size / 1024, 2),
                    "Định dạng": uf.name.split(".")[-1].lower(),
                    "Trạng thái": "Sẵn sàng (QUEUED)"
                })
            st.dataframe(file_preview_data, use_container_width=True)

            # --- QUY TRÌNH 5 BƯỚC KHÁM PHÁ & ÁNH XẠ CƠ SỞ DỮ LIỆU SQLITE ---
            sqlite_files = [uf for uf in uploaded_batch_files if uf.name.lower().endswith((".db", ".sqlite"))]
            if sqlite_files:
                with st.container(border=True):
                    st.markdown("### 🗄️ Khám Phá & Ánh Xạ Cơ Sở Dữ Liệu SQLite (.db, .sqlite)")
                    st.caption(
                        "Hệ thống hỗ trợ nạp cơ sở dữ liệu SQLite từ nhiều nguồn (từ điển, hỏi-đáp, danh mục). "
                        "Vui lòng thực hiện các bước dưới đây để kiểm tra cấu trúc và ánh xạ sang schema chuẩn hóa."
                    )

                    # Chọn tệp SQLite cần cấu hình nếu có nhiều hơn 1 tệp
                    if len(sqlite_files) > 1:
                        target_uf = st.selectbox(
                            "Chọn tệp SQLite để cấu hình:",
                            options=sqlite_files,
                            format_func=lambda x: f"{x.name} ({round(x.size / 1024, 2)} KB)",
                            key="sb_select_active_sqlite_file"
                        )
                    else:
                        target_uf = sqlite_files[0]

                    # Ghi tạm vào thư mục raw để inspect cấu trúc
                    import hashlib
                    target_bytes = target_uf.getvalue()
                    target_hash = hashlib.sha256(target_bytes).hexdigest()
                    inspect_temp_path = settings.RAW_DATA_DIR / f"inspect_{target_hash[:8]}_{target_uf.name}"
                    settings.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
                    if not inspect_temp_path.exists() or inspect_temp_path.stat().st_size != len(target_bytes):
                        with open(inspect_temp_path, "wb") as f_tmp:
                            f_tmp.write(target_bytes)

                    sqlite_loader = SQLiteLoader()
                    schema_info = sqlite_loader.inspect_schema(inspect_temp_path)

                    # BƯỚC 1: KIỂM TRA TỆP
                    st.markdown("#### 1️⃣ Bước 1 — Kiểm Tra Tính Toàn Vẹn Tệp")
                    if not schema_info.is_valid:
                        st.error(f"❌ Tệp SQLite không hợp lệ hoặc bị hỏng: {schema_info.error_message}")
                    else:
                        col_v1, col_v2, col_v3 = st.columns(3)
                        col_v1.metric("Tên tệp", target_uf.name)
                        col_v2.metric("Dung lượng", f"{round(target_uf.size / 1024, 2)} KB")
                        col_v3.metric("Số bảng dữ liệu", len(schema_info.tables))
                        st.success(
                            f"✅ **Kiểm tra thành công**: Tệp SQLite hợp lệ (Header chuẩn, PRAGMA quick_check: OK, Chế độ: Chỉ đọc). "
                            f"Mã băm SHA-256: `{target_hash[:16]}...`"
                        )

                        # BƯỚC 2: KHÁM PHÁ CẤU TRÚC
                        st.markdown("#### 2️⃣ Bước 2 — Khám Phá Cấu Trúc Bảng & Cột")
                        table_names = list(schema_info.tables.keys())
                        selected_table_name = st.selectbox(
                            "Chọn bảng dữ liệu chính để kiểm tra / nạp:",
                            options=table_names,
                            key=f"sb_table_{target_hash[:8]}"
                        )
                        selected_table = schema_info.tables[selected_table_name]

                        col_t1, col_t2 = st.columns([1, 1])
                        with col_t1:
                            st.write(f"**Danh sách cột của bảng `{selected_table_name}` ({len(selected_table.columns)} cột):**")
                            col_display = []
                            for c in selected_table.columns:
                                col_display.append({
                                    "Tên cột": c.name,
                                    "Kiểu dữ liệu": c.data_type,
                                    "Khóa chính (PK)": "Có" if c.is_pk else "Không",
                                    "NOT NULL": "Có" if c.not_null else "Không"
                                })
                            st.dataframe(col_display, use_container_width=True, height=180)

                        with col_t2:
                            st.write(f"**Tổng số dòng:** {selected_table.row_count:,} dòng")
                            if selected_table.foreign_keys:
                                st.info(
                                    "🔗 **Khóa ngoại (Foreign Keys):**\n" +
                                    "\n".join([f"- Cột `{fk.from_col}` ➔ Bảng `{fk.table}` (`{fk.to_col}`)" for fk in selected_table.foreign_keys])
                                )
                            else:
                                st.caption("Bảng này không có khai báo khóa ngoại trực tiếp.")

                        if selected_table.sample_rows:
                            with st.expander(f"👀 Xem trước dữ liệu gốc bảng `{selected_table_name}` (5 dòng đầu)", expanded=False):
                                st.dataframe(selected_table.sample_rows, use_container_width=True)

                        # BƯỚC 3: CHỌN CÁCH NHẬP DỮ LIỆU & ÁNH XẠ CỘT
                        st.markdown("#### 3️⃣ Bước 3 — Chọn Cách Nhập & Ánh Xạ Cột Sang QARecord")

                        # Gợi ý mapping tự động từ schema
                        auto_cfg = sqlite_loader.auto_detect_mapping(schema_info)
                        auto_mode_idx = 0
                        if auto_cfg:
                            if auto_cfg.mode == SQLiteMappingMode.VOCAB:
                                auto_mode_idx = 0
                            elif auto_cfg.mode == SQLiteMappingMode.QA:
                                auto_mode_idx = 1
                            elif auto_cfg.mode == SQLiteMappingMode.RELATIONAL:
                                auto_mode_idx = 2

                        map_mode_label = st.radio(
                            "Chọn dạng cấu trúc dữ liệu của database:",
                            options=[
                                "📚 Dữ liệu Từ vựng (Vocabulary: Từ, Nghĩa, IPA, Từ loại, Ví dụ)",
                                "💬 Dữ liệu Hỏi - Đáp (Q&A: Câu hỏi, Câu trả lời, Trình độ)",
                                "🔗 Dữ liệu Quan hệ nhiều bảng (Relational: Ghép bảng cha - con qua khóa ngoại)"
                            ],
                            index=auto_mode_idx,
                            key=f"rb_mode_{target_hash[:8]}"
                        )

                        col_options = ["(Bỏ qua / Không có)"] + [c.name for c in selected_table.columns]
                        chosen_config = None

                        def _match_col_name(candidates, cols):
                            for cand in candidates:
                                for c in cols:
                                    if c.lower() == cand.lower():
                                        return c
                            return None

                        if "Dữ liệu Từ vựng" in map_mode_label:
                            st.caption("Ánh xạ các cột trong bảng sang trường từ vựng. Cột Từ vựng và Nghĩa là bắt buộc.")
                            col_v1, col_v2, col_v3 = st.columns(3)

                            default_w = _match_col_name(["word", "tu_vung", "vocab", "term", "english"], [c.name for c in selected_table.columns])
                            default_def = _match_col_name(["definition", "dinh_nghia", "meaning", "nghia", "vietnamese"], [c.name for c in selected_table.columns])
                            default_ipa = _match_col_name(["ipa", "phien_am", "pronunciation"], [c.name for c in selected_table.columns])
                            default_pos = _match_col_name(["pos", "tu_loai", "part_of_speech", "type"], [c.name for c in selected_table.columns])
                            default_ex = _match_col_name(["example", "vi_du", "sentence"], [c.name for c in selected_table.columns])
                            default_lvl = _match_col_name(["level", "trinh_do", "cefr"], [c.name for c in selected_table.columns])

                            with col_v1:
                                w_idx = col_options.index(default_w) if default_w in col_options else 1
                                sel_w = st.selectbox("Từ tiếng Anh (Word) *:", options=col_options[1:], index=max(0, w_idx - 1), key=f"sel_w_{target_hash[:8]}")
                                ipa_idx = col_options.index(default_ipa) if default_ipa in col_options else 0
                                sel_ipa = st.selectbox("Phiên âm (IPA):", options=col_options, index=ipa_idx, key=f"sel_ipa_{target_hash[:8]}")

                            with col_v2:
                                def_idx = col_options.index(default_def) if default_def in col_options else 1
                                sel_def = st.selectbox("Nghĩa tiếng Việt (Definition) *:", options=col_options[1:], index=max(0, def_idx - 1), key=f"sel_def_{target_hash[:8]}")
                                pos_idx = col_options.index(default_pos) if default_pos in col_options else 0
                                sel_pos = st.selectbox("Từ loại (Part of Speech):", options=col_options, index=pos_idx, key=f"sel_pos_{target_hash[:8]}")

                            with col_v3:
                                ex_idx = col_options.index(default_ex) if default_ex in col_options else 0
                                sel_ex = st.selectbox("Ví dụ minh họa (Example):", options=col_options, index=ex_idx, key=f"sel_ex_{target_hash[:8]}")
                                lvl_idx = col_options.index(default_lvl) if default_lvl in col_options else 0
                                sel_lvl = st.selectbox("Trình độ (Level/CEFR):", options=col_options, index=lvl_idx, key=f"sel_lvl_{target_hash[:8]}")

                            chosen_config = SQLiteMappingConfig(
                                mode=SQLiteMappingMode.VOCAB,
                                primary_table=selected_table_name,
                                word_col=sel_w,
                                definition_col=sel_def,
                                ipa_col=sel_ipa if sel_ipa != "(Bỏ qua / Không có)" else None,
                                pos_col=sel_pos if sel_pos != "(Bỏ qua / Không có)" else None,
                                example_col=sel_ex if sel_ex != "(Bỏ qua / Không có)" else None,
                                level_col=sel_lvl if sel_lvl != "(Bỏ qua / Không có)" else None,
                            )

                        elif "Dữ liệu Hỏi - Đáp" in map_mode_label:
                            st.caption("Ánh xạ cột Câu hỏi và Câu trả lời trực tiếp sang QARecord.")
                            col_q1, col_q2 = st.columns(2)

                            default_q = _match_col_name(["question", "cau_hoi", "query", "prompt"], [c.name for c in selected_table.columns])
                            default_a = _match_col_name(["answer", "cau_tra_loi", "tra_loi", "response", "content"], [c.name for c in selected_table.columns])
                            default_w = _match_col_name(["word", "tu_vung", "vocab", "term"], [c.name for c in selected_table.columns])
                            default_lvl = _match_col_name(["level", "trinh_do", "cefr"], [c.name for c in selected_table.columns])

                            with col_q1:
                                q_idx = col_options.index(default_q) if default_q in col_options else 1
                                sel_q = st.selectbox("Cột Câu hỏi (Question) *:", options=col_options[1:], index=max(0, q_idx - 1), key=f"sel_q_{target_hash[:8]}")
                                w_idx = col_options.index(default_w) if default_w in col_options else 0
                                sel_qw = st.selectbox("Cột Từ vựng/Chủ đề (Word):", options=col_options, index=w_idx, key=f"sel_qw_{target_hash[:8]}")

                            with col_q2:
                                a_idx = col_options.index(default_a) if default_a in col_options else 1
                                sel_a = st.selectbox("Cột Câu trả lời (Answer) *:", options=col_options[1:], index=max(0, a_idx - 1), key=f"sel_a_{target_hash[:8]}")
                                lvl_idx = col_options.index(default_lvl) if default_lvl in col_options else 0
                                sel_qlvl = st.selectbox("Cột Trình độ (Level):", options=col_options, index=lvl_idx, key=f"sel_qlvl_{target_hash[:8]}")

                            chosen_config = SQLiteMappingConfig(
                                mode=SQLiteMappingMode.QA,
                                primary_table=selected_table_name,
                                question_col=sel_q,
                                answer_col=sel_a,
                                word_col=sel_qw if sel_qw != "(Bỏ qua / Không có)" else None,
                                level_col=sel_qlvl if sel_qlvl != "(Bỏ qua / Không có)" else None,
                            )

                        else:
                            # Chế độ RELATIONAL
                            st.caption("Kết hợp bảng chính (ví dụ words) và bảng liên kết (ví dụ definitions) qua khóa ngoại an toàn.")
                            other_tables = [t for t in table_names if t != selected_table_name]
                            if not other_tables:
                                st.warning("Database chỉ có 1 bảng duy nhất. Vui lòng chọn chế độ Từ vựng hoặc Hỏi - Đáp.")
                            else:
                                col_r1, col_r2 = st.columns(2)
                                with col_r1:
                                    sel_related_table = st.selectbox(
                                        "Bảng liên kết chứa định nghĩa (Child table):",
                                        options=other_tables,
                                        key=f"sel_rel_t_{target_hash[:8]}"
                                    )
                                    rel_table_info = schema_info.tables[sel_related_table]

                                with col_r2:
                                    # Tìm khóa ngoại gợi ý
                                    suggested_fk = None
                                    for fk in rel_table_info.foreign_keys:
                                        if fk.table.lower() == selected_table_name.lower():
                                            suggested_fk = fk.from_col
                                            break
                                    rel_cols = [c.name for c in rel_table_info.columns]
                                    fk_idx = rel_cols.index(suggested_fk) if suggested_fk in rel_cols else 0
                                    sel_fk_col = st.selectbox(
                                        f"Khóa ngoại trong bảng `{sel_related_table}` trỏ tới `{selected_table_name}`:",
                                        options=rel_cols,
                                        index=fk_idx,
                                        key=f"sel_fk_{target_hash[:8]}"
                                    )

                                col_p1, col_p2 = st.columns(2)
                                with col_p1:
                                    p_word_cols = [c.name for c in selected_table.columns]
                                    sel_rel_w = st.selectbox(f"Cột Từ tiếng Anh trong bảng `{selected_table_name}` *:", options=p_word_cols, key=f"sel_rel_w_{target_hash[:8]}")
                                with col_p2:
                                    r_def_cols = [c.name for c in rel_table_info.columns]
                                    sel_rel_def = st.selectbox(f"Cột Định nghĩa trong bảng `{sel_related_table}` *:", options=r_def_cols, key=f"sel_rel_def_{target_hash[:8]}")

                                chosen_config = SQLiteMappingConfig(
                                    mode=SQLiteMappingMode.RELATIONAL,
                                    primary_table=selected_table_name,
                                    related_table=sel_related_table,
                                    foreign_key_parent_col="id",
                                    foreign_key_child_col=sel_fk_col,
                                    word_col=sel_rel_w,
                                    definition_col=sel_rel_def,
                                )

                        # BƯỚC 4: XEM TRƯỚC DỮ LIỆU CHUẨN HÓA (QARECORD PREVIEW)
                        if chosen_config:
                            st.markdown("#### 4️⃣ Bước 4 — Xem Trước Dữ Liệu Sau Chuẩn Hóa (QARecord Preview)")
                            try:
                                preview_recs = sqlite_loader.preview_records(inspect_temp_path, chosen_config, limit=5)
                                if preview_recs:
                                    preview_table = []
                                    for pr in preview_recs:
                                        preview_table.append({
                                            "Mã bản ghi": pr.record_id,
                                            "Từ vựng": pr.word,
                                            "Câu hỏi": pr.question,
                                            "Câu trả lời chuẩn hóa": (pr.answer[:120] + "...") if len(pr.answer) > 120 else pr.answer,
                                            "Trình độ": pr.level or "N/A",
                                            "Bảng / Nguồn": f"{pr.sheet} ({pr.source})"
                                        })
                                    st.dataframe(preview_table, use_container_width=True)
                                    st.success(
                                        f"✅ Đã trích xuất thử nghiệm thành công {len(preview_recs)} bản ghi mẫu. "
                                        f"Dữ liệu đã sẵn sàng để nạp vào Knowledge Base ở Bước 5 bên dưới."
                                    )
                                    # Lưu cấu hình vào session_state để dùng khi nạp
                                    st.session_state.sqlite_configs[target_hash] = chosen_config
                                    st.session_state.sqlite_configs[target_uf.name] = chosen_config
                                else:
                                    st.warning("⚠️ Không tìm thấy bản ghi hợp lệ nào với cấu hình ánh xạ hiện tại.")
                            except Exception as prev_err:
                                st.error(f"❌ Lỗi khi xem trước dữ liệu: {prev_err}")

            col_m1, col_m2 = st.columns([1, 1])
            with col_m1:
                ingestion_mode = st.radio(
                    "Chế độ nạp dữ liệu:",
                    options=["ADD (Bổ sung)", "REPLACE (Thay thế toàn bộ)"],
                    index=0,
                    help="ADD: Bổ sung dữ liệu mới và cập nhật bản ghi nếu trùng ID. REPLACE: Xóa dữ liệu cũ và xây dựng lại từ đầu."
                )
                is_replace_mode = "REPLACE" in ingestion_mode

            with col_m2:
                if not is_replace_mode:
                    st.info(
                        "📌 **Chế độ ADD**: Bổ sung tệp mới vào kho tri thức hiện tại. "
                        "Các bản ghi trùng lặp nội dung sẽ được tự động bỏ qua."
                    )
                else:
                    st.warning(
                        "⚠️ **Chế độ REPLACE**: Thao tác này sẽ xóa toàn bộ kho tri thức hiện có và xây dựng lại từ các tệp này. "
                        "Hệ thống sẽ sao lưu snapshot dự phòng trước khi thay thế."
                    )

            # Lớp bảo vệ UI Guard: Bắt buộc xác nhận trước khi cho phép REPLACE
            can_proceed = True
            if is_replace_mode:
                confirm_replace = st.checkbox(
                    "⚠️ Tôi xác nhận muốn THAY THẾ TOÀN BỘ kho tri thức hiện tại bằng các tệp này.",
                    key="cb_confirm_replace"
                )
                can_proceed = confirm_replace
                if not can_proceed:
                    st.caption("🔒 Nút xử lý bị khóa cho đến khi bạn tích chọn xác nhận bên trên.")

            # Kiểm tra trạng thái điều phối tài nguyên để chống xung đột thao tác
            from src.resource.manager import ResourceState, get_resource_manager
            rm = get_resource_manager()
            is_indexing_now = rm.state in (ResourceState.INDEXING_CPU, ResourceState.INDEXING_GPU, ResourceState.RESTORING_CHAT)
            if is_indexing_now or st.session_state.is_ingesting:
                st.warning("⏳ Hệ thống đang có một tiến trình lập chỉ mục đang chạy. Vui lòng đợi hoàn tất trước khi nạp thêm.")

            # Nút bấm bắt đầu xử lý
            if st.button(
                "🚀 Bắt Đầu Xử Lý Batch Tệp",
                key="btn_process_batch_all",
                type="primary",
                disabled=(not can_proceed) or is_indexing_now or st.session_state.is_ingesting,
                use_container_width=True
            ):
                st.session_state.is_ingesting = True
                settings.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
                saved_paths: List[Path] = []
                seen_upload_hashes: Dict[str, str] = {}

                # Quét mã băm hiện có trong data/raw/ để kiểm tra trùng lặp
                existing_raw_by_hash: Dict[str, Path] = {}
                for p in settings.RAW_DATA_DIR.iterdir():
                    if p.is_file() and not p.name.startswith(".git") and p.name != "dictionary_en_vi.db":
                        try:
                            import hashlib
                            h = hashlib.sha256(p.read_bytes()).hexdigest()
                            existing_raw_by_hash[h] = p
                        except Exception:
                            pass

                for uf in uploaded_batch_files:
                    content_bytes = uf.getvalue()
                    import hashlib
                    uf_hash = hashlib.sha256(content_bytes).hexdigest()

                    # 1. Trùng lặp trong cùng đợt tải: Tuyệt đối không lưu vào raw
                    if uf_hash in seen_upload_hashes:
                        continue

                    seen_upload_hashes[uf_hash] = uf.name

                    # 2. Trùng lặp với tệp đã có trong raw hoặc active sources: Không lưu vào raw
                    existing_file = existing_raw_by_hash.get(uf_hash)
                    if not is_replace_mode and (existing_file or batch_manager.is_duplicate_file(uf_hash)):
                        continue

                    # 3. Tệp hợp lệ: Lưu đúng tên gốc, nếu cùng tên ghi đè cập nhật (không sinh tệp rác raw_...)
                    target_path = settings.RAW_DATA_DIR / uf.name
                    with open(target_path, "wb") as f:
                        f.write(content_bytes)
                    saved_paths.append(target_path)
                    existing_raw_by_hash[uf_hash] = target_path

                progress_bar = st.progress(0, text="Đang khởi tạo tiến trình nạp...")

                def ui_batch_callback(msg: str, pct: float, current_res: Optional[Any] = None):
                    clamped_pct = max(0.0, min(1.0, float(pct)))
                    progress_bar.progress(int(clamped_pct * 100), text=msg)

                selected_mode_str = "replace" if is_replace_mode else "add"

                try:
                    report = batch_manager.ingest_batch(
                        files=saved_paths,
                        mode=selected_mode_str,
                        progress_callback=ui_batch_callback,
                        sqlite_mappings=st.session_state.get("sqlite_configs", {})
                    )
                    st.session_state.batch_report = report

                    b_status = getattr(report, "batch_status", BatchStatus.FAILED)
                    status_val = b_status.value if hasattr(b_status, "value") else str(b_status)

                    if status_val == BatchStatus.SUCCESS.value:
                        new_records = batch_manager.loader.load_from_jsonl()
                        engine.update_knowledge_base(new_records)
                        progress_bar.progress(100, text="Hoàn tất xử lý batch thành công!")
                        st.success("Đã hoàn tất xử lý và cập nhật kho tri thức thành công!")
                        st.toast("Hoàn tất xử lý Batch!", icon="🎉")
                        # Làm mới uploader khi thành công hoàn toàn
                        st.session_state.sqlite_configs = {}
                        st.session_state.uploader_generation += 1
                    elif status_val == BatchStatus.PARTIAL_SUCCESS.value:
                        new_records = batch_manager.loader.load_from_jsonl()
                        engine.update_knowledge_base(new_records)
                        progress_bar.progress(100, text="Xử lý hoàn tất một phần (Có tệp bị bỏ qua hoặc lỗi).")
                        st.warning("Hoàn tất xử lý một phần: Một số tệp đã được thêm, một số tệp bị bỏ qua hoặc lỗi.")
                        st.toast("Xử lý hoàn tất một phần!", icon="⚠️")
                        # Làm mới uploader để người dùng có thể nạp tệp mới
                        st.session_state.sqlite_configs = {}
                        st.session_state.uploader_generation += 1
                    else:
                        progress_bar.progress(100, text="Xử lý batch thất bại. Dữ liệu cũ được bảo toàn.")
                        st.error(
                            "Batch ingestion thất bại hoặc thao tác thay thế bị hủy bỏ. "
                            "Kho tri thức cũ được bảo toàn nguyên vẹn."
                        )
                        # Khi FAILED: giữ nguyên uploader_generation để người dùng thử lại danh sách tệp
                except Exception as batch_err:
                    logger.error("Lỗi trong quá trình thực thi batch ingestion: %s", batch_err, exc_info=True)
                    st.error(f"Đã xảy ra sự sự cố nghiêm trọng khi nạp dữ liệu: {batch_err}")
                finally:
                    st.session_state.is_ingesting = False
                    for tmp_inspect in settings.RAW_DATA_DIR.glob("inspect_*"):
                        try:
                            tmp_inspect.unlink(missing_ok=True)
                        except Exception:
                            pass

                st.rerun()

    # 2. Báo cáo kết quả xử lý Batch gần nhất
    report = st.session_state.batch_report
    if report:
        with st.container(border=True):
            st.subheader("📊 Báo Cáo Xử Lý Batch Gần Nhất")
            b_status = getattr(report, "batch_status", BatchStatus.FAILED)
            status_val = b_status.value if hasattr(b_status, "value") else str(b_status)

            col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
            col_s1.metric("Tổng số tệp", report.total_files)
            col_s2.metric("Thành công", report.success_count)
            col_s3.metric("Bỏ qua", report.skipped_count)
            col_s4.metric("Thất bại", report.failed_count)
            col_s5.metric("Trạng thái", status_val)

            if getattr(report, "file_results", None):
                with st.expander("Chi tiết kết quả từng tệp", expanded=True):
                    detail_rows = []
                    for fr in report.file_results:
                        detail_rows.append({
                            "Tên tệp": fr.file_name,
                            "Trạng thái": fr.status.value if hasattr(fr.status, "value") else str(fr.status),
                            "Bản ghi trích xuất": fr.records_extracted,
                            "Bản ghi thêm mới": fr.records_added,
                            "Trùng lặp": fr.duplicates_skipped,
                            "Lý do / Hành động": fr.reason or "Hoàn tất",
                        })
                    st.dataframe(detail_rows, use_container_width=True)

    # 3. Thống kê trạng thái lưu trữ độc lập
    with st.container(border=True):
        st.subheader("📦 Trạng Thái Lưu Trữ & Chỉ Mục Độc Lập")
        st.caption("Các tầng lưu trữ và chỉ mục được quản lý riêng biệt, phản ánh số liệu thực tế:")

        storage_stats = inspect_storage_metrics(engine)
        col_k1, col_k2, col_k3, col_k4 = st.columns(4)

        with col_k1:
            with st.container(border=True):
                val_html = (
                    f'<div class="stat-card-value">{storage_stats["jsonl_disk_count"]:,} dòng</div>'
                    f'<div class="stat-card-caption">data/processed/qa_records.jsonl</div>'
                    if storage_stats["jsonl_disk_count"] is not None
                    else f'<div class="stat-card-error">⚠️ {storage_stats["jsonl_disk_error"]}</div>'
                )
                st.markdown(
                    f'<div class="stat-card-label">Tệp JSONL Trên Đĩa</div>{val_html}',
                    unsafe_allow_html=True
                )

        with col_k2:
            with st.container(border=True):
                val_html = (
                    f'<div class="stat-card-value">{storage_stats["engine_records_count"]:,} bản ghi</div>'
                    f'<div class="stat-card-caption">QARecord nạp trong RAM</div>'
                    if storage_stats["engine_records_count"] is not None
                    else f'<div class="stat-card-error">⚠️ {storage_stats["engine_records_error"]}</div>'
                )
                st.markdown(
                    f'<div class="stat-card-label">Bộ Nhớ ChatEngine</div>{val_html}',
                    unsafe_allow_html=True
                )

        with col_k3:
            with st.container(border=True):
                val_html = (
                    f'<div class="stat-card-value">{storage_stats["chroma_count"]:,} vectors</div>'
                    f'<div class="stat-card-caption">Chỉ mục BGE-M3 (1024-d)</div>'
                    if storage_stats["chroma_count"] is not None
                    else f'<div class="stat-card-error">⚠️ {storage_stats["chroma_error"]}</div>'
                )
                st.markdown(
                    f'<div class="stat-card-label">ChromaDB Vector</div>{val_html}',
                    unsafe_allow_html=True
                )

        with col_k4:
            with st.container(border=True):
                val_html = (
                    f'<div class="stat-card-value">{storage_stats["bm25_count"]:,} mục</div>'
                    f'<div class="stat-card-caption">Inverted Index từ khóa</div>'
                    if storage_stats["bm25_count"] is not None
                    else f'<div class="stat-card-error">⚠️ {storage_stats["bm25_error"]}</div>'
                )
                st.markdown(
                    f'<div class="stat-card-label">BM25 Lexical Index</div>{val_html}',
                    unsafe_allow_html=True
                )

        indices_ready = (
            storage_stats["engine_records_count"] is not None and storage_stats["engine_records_count"] > 0 and
            storage_stats["chroma_count"] is not None and storage_stats["chroma_count"] > 0 and
            storage_stats["bm25_count"] is not None and storage_stats["bm25_count"] > 0
        )
        indices_empty = (
            storage_stats["jsonl_disk_count"] == 0 and
            storage_stats["engine_records_count"] == 0 and
            storage_stats["chroma_count"] == 0 and
            storage_stats["bm25_count"] == 0
        )
        if indices_ready:
            st.success("🟢 Toàn bộ 3 chỉ mục (JSONL, ChromaDB, BM25) đã được tải và sẵn sàng phục vụ tra cứu.")
        elif indices_empty:
            st.info("ℹ️ Trạng thái Knowledge Base: Trống (Empty) — Toàn bộ dữ liệu đã được làm sạch hoặc chưa có tài liệu nào được nạp.")
        else:
            st.warning("⚠️ Một hoặc nhiều tầng chỉ mục chưa sẵn sàng hoặc rỗng. Vui lòng kiểm tra lại dữ liệu.")

        st.caption(
            "💡 *Lưu ý kỹ thuật: Số lượng bản ghi JSONL, BM25 và ChromaDB vector được quản lý độc lập theo cơ chế "
            "khử trùng lặp và chunking của từng tầng lưu trữ và không nhất thiết phải có tỷ lệ 1:1.*"
        )

    # 4. Danh sách các nguồn dữ liệu đang hoạt động (Active Sources)
    active_sources = batch_manager.get_active_sources()
    with st.container(border=True):
        st.subheader("📚 Nguồn Dữ Liệu Đang Hoạt Động (Active Sources)")
        if active_sources:
            src_table = []
            for s in active_sources:
                display_name = s.get("source_name") or s.get("file_name") or "Chưa rõ tên nguồn (Thiếu metadata)"
                src_table.append({
                    "Tên nguồn": display_name,
                    "Mã băm SHA-256": s.get("file_hash", "")[:12] + "..." if s.get("file_hash") else "Không có mã băm",
                    "Số bản ghi": s.get("record_count", 0),
                    "Thời gian nạp": s.get("ingested_at", "Không rõ"),
                    "Trạng thái": s.get("status", "ACTIVE"),
                })
            st.dataframe(src_table, use_container_width=True)
        else:
            st.info("ℹ️ Không có nguồn dữ liệu nào đang hoạt động trong Knowledge Base.")

    # 5. Xóa toàn bộ dữ liệu Knowledge Base (Danger Zone)
    with st.container(border=True):
        st.subheader("🗑️ Xóa Toàn Bộ Dữ Liệu Knowledge Base")
        st.markdown(
            """
            Khu vực này cho phép người quản trị xóa toàn bộ dữ liệu tri thức đã nạp và đưa Knowledge Base về trạng thái rỗng ban đầu để nạp bộ dữ liệu hoàn toàn mới.

            **Hậu quả khi thực hiện thao tác xóa:**
            - **Xóa toàn bộ dữ liệu từ vựng đã nạp** trong tệp chuẩn hóa `data/processed/qa_records.jsonl`.
            - **Xóa các chỉ mục tìm kiếm tương ứng**: Giải phóng collection vector trong ChromaDB và đặt lại chỉ mục từ khóa BM25 / Lexical Matcher.
            - **Xóa manifest và danh sách nguồn dữ liệu đang hoạt động** trong `sources_manifest.json`.
            - **Xóa các bản sao tệp nguồn** được tải lên và quản lý riêng bởi Knowledge Base.
            - **Sau khi hoàn tất, chatbot không còn tra cứu được dữ liệu đã xóa** cho đến khi bạn nạp bộ dữ liệu mới.

            *(Tuyệt đối bảo vệ: Cơ sở dữ liệu từ điển hệ thống `dictionary_en_vi.db`, mô hình AI PhoBERT/BGE-M3/Qwen và mã nguồn ứng dụng sẽ được giữ nguyên 100%.)*
            """
        )

        from src.resource.manager import ResourceState, get_resource_manager
        rm = get_resource_manager()
        is_indexing_now = rm.state in (ResourceState.INDEXING_CPU, ResourceState.INDEXING_GPU, ResourceState.RESTORING_CHAT)

        if not st.session_state.get("show_clear_kb_confirm", False):
            if st.button(
                "🗑️ Bắt Đầu Quy Trình Xóa Toàn Bộ Knowledge Base",
                key="btn_open_clear_kb_confirm",
                type="secondary",
                disabled=is_indexing_now or st.session_state.is_ingesting,
                help="Nhấn để mở các bước xác nhận bảo mật trước khi xóa."
            ):
                if is_indexing_now or st.session_state.is_ingesting:
                    st.error("⏳ Hệ thống đang có tiến trình lập chỉ mục/nạp dữ liệu đang chạy. Vui lòng đợi hoàn tất trước khi xóa.")
                else:
                    st.session_state.show_clear_kb_confirm = True
                    st.rerun()
        else:
            # HỘP XÁC NHẬN BẢO MẬT NHIỀU BƯỚC
            with st.container(border=True):
                st.error(
                    "⚠️ **CẢNH BÁO NGUY HIỂM — THAO TÁC XÓA DỮ LIỆU TRÊN Ổ ĐĨA**\n\n"
                    "Thao tác này sẽ xóa vĩnh viễn dữ liệu tri thức trên ổ đĩa vật lý và **không thể khôi phục** nếu bạn không có bản sao lưu bên ngoài. "
                    "Vui lòng thực hiện tuần tự 3 bước sau:"
                )

                st.markdown(
                    "**Bước 1:** Đọc kỹ cảnh báo hậu quả xóa dữ liệu ở trên.\n\n"
                    "**Bước 2:** Tích vào ô xác nhận bên dưới để mở khóa thao tác xóa vĩnh viễn:"
                )

                confirm_cb = st.checkbox(
                    "⚠️ Tôi xác nhận hiểu rõ hậu quả và đồng ý XÓA TOÀN BỘ dữ liệu Knowledge Base trên ổ đĩa.",
                    key="cb_confirm_clear_kb"
                )

                st.markdown("**Bước 3:** Nhấn nút xác nhận xóa lần cuối hoặc hủy bỏ:")

                col_c1, col_c2 = st.columns([1, 1])
                with col_c1:
                    btn_execute_clear = st.button(
                        "💥 XÁC NHẬN XÓA TOÀN BỘ KNOWLEDGE BASE",
                        key="btn_execute_clear_kb_final",
                        type="primary",
                        disabled=(not confirm_cb) or is_indexing_now or st.session_state.is_ingesting,
                        use_container_width=True
                    )
                with col_c2:
                    if st.button("❌ Hủy Bỏ Thao Tác", key="btn_cancel_clear_kb", use_container_width=True):
                        st.session_state.show_clear_kb_confirm = False
                        st.rerun()

                if btn_execute_clear:
                    if is_indexing_now or st.session_state.is_ingesting:
                        st.error("⏳ Không thể thực hiện: Hệ thống đang có tiến trình lập chỉ mục đang chạy. Vui lòng đợi hoàn tất.")
                    else:
                        with st.spinner("Đang thực hiện xóa toàn bộ dữ liệu Knowledge Base và đồng bộ các chỉ mục..."):
                            # Đảm bảo batch_manager luôn có hàm clear_knowledge_base ngay cả khi tiến trình Streamlit chưa khởi động lại
                            if not hasattr(batch_manager, "clear_knowledge_base"):
                                import importlib
                                import src.data.batch_ingestion as _bmi_mod
                                importlib.reload(_bmi_mod)
                                batch_manager = _bmi_mod.BatchIngestionManager()

                            result = batch_manager.clear_knowledge_base(engine=engine)

                        if result.get("success", False) or result.get("status") == "SUCCESS":
                            # Cập nhật RAM và trạng thái ChatEngine
                            if hasattr(engine, "clear_knowledge_base"):
                                engine.clear_knowledge_base()
                            else:
                                engine.update_knowledge_base([])
                                if hasattr(engine, "tracker") and hasattr(engine.tracker, "clear"):
                                    engine.tracker.clear()

                            # Làm mới cache_resource nếu cần
                            try:
                                get_chatbot_engine.clear()
                            except Exception:
                                pass

                            # Đưa session state về trạng thái sẵn sàng nhận dữ liệu mới
                            st.session_state.messages = []
                            st.session_state.batch_report = None
                            st.session_state.sqlite_configs = {}
                            st.session_state.uploader_generation += 1
                            st.session_state.show_clear_kb_confirm = False
                            st.session_state.status = "Knowledge Base đã được làm sạch hoàn toàn!"

                            # Ghi nhận vào nhật ký kiểm toán (Audit Log)
                            import time as _time
                            audit_entry = {
                                "timestamp": _time.strftime("%Y-%m-%d %H:%M:%S"),
                                "action": "CLEAR_KNOWLEDGE_BASE",
                                "detail": (
                                    f"Đã xóa toàn bộ Knowledge Base: {result.get('deleted_records', 0)} bản ghi, "
                                    f"{result.get('deleted_sources', 0)} nguồn, "
                                    f"{len(result.get('deleted_raw_files', []))} tệp nguồn. Tất cả chỉ mục về 0."
                                ),
                                "status": "SUCCESS"
                            }
                            st.session_state.audit_logs.append(audit_entry)

                            st.success(
                                f"✅ {result.get('message', 'Đã xóa toàn bộ dữ liệu Knowledge Base thành công.')} "
                                f"(Đã xóa: {result.get('deleted_records', 0)} bản ghi, "
                                f"{result.get('deleted_sources', 0)} nguồn dữ liệu)."
                            )
                            st.toast("Đã xóa toàn bộ dữ liệu Knowledge Base!", icon="🗑️")
                            _time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(
                                f"❌ Thao tác xóa thất bại: {result.get('message', 'Lỗi không xác định')}. "
                                f"Dữ liệu đã được rollback bảo vệ an toàn."
                            )


elif st.session_state.nav_page in ("📈 Chẩn đoán", "📈 Chẩn đoán & Nhật ký"):
    # --------------------------------------------------------------------------
    # TRANG 3: 📈 CHẨN ĐOÁN & NHẬT KÝ (DIAGNOSTICS & AUDIT - ADMIN ONLY)
    # --------------------------------------------------------------------------
    col_ret_1, col_ret_2 = st.columns([1, 5])
    with col_ret_1:
        if st.button("← Trò chuyện", key="btn_ret_from_admin_diag"):
            st.session_state.nav_page = "💬 Tra cứu từ vựng"
            st.rerun()

    try:
        auth_service.require_admin(current_user)
    except PermissionError as perm_err:
        st.error(f"❌ Truy cập bị từ chối: Yêu cầu quyền Quản trị viên (Admin) để xem chẩn đoán hệ thống.")
        st.stop()

    with st.container(border=True):
        st.markdown('<div class="panel-card-header">📈 Chẩn Đoán Hệ Thống & Kiểm Định Kỹ Thuật</div>', unsafe_allow_html=True)

        # 1. Bộ điều phối tài nguyên & Telemetry thời gian thực
        st.markdown("#### 1. Bộ Điều Phối Tài Nguyên & Telemetry Thời Gian Thực (Resource Manager)")
        from src.resource.manager import ResourceState, get_resource_manager
        rm = get_resource_manager()
        vram_data = rm.telemetry.get_vram_info()
        ram_data = rm.telemetry.get_ram_info()
        cpu_data = rm.telemetry.get_cpu_info()

        # Hiển thị trạng thái hệ thống bằng màu sắc trực quan
        state_colors = {
            ResourceState.CHAT_READY: ("🟢 Sẵn Sàng (CHAT_READY)", "#16A34A", "Qwen ưu tiên GPU, BGE chạy CPU"),
            ResourceState.INDEXING_CPU: ("🟡 Nạp CPU (INDEXING_CPU)", "#CA8A04", "Nạp dữ liệu trên CPU, Chat an toàn"),
            ResourceState.INDEXING_GPU: ("🔵 Tăng Tốc GPU (INDEXING_GPU)", "#2563EB", "BGE chạy CUDA, Qwen tạm giải phóng"),
            ResourceState.RESTORING_CHAT: ("🟠 Khôi Phục (RESTORING_CHAT)", "#EA580C", "Đang nạp lại Qwen vào VRAM"),
            ResourceState.RECOVERY_FAILED: ("🔴 Lỗi Khôi Phục (RECOVERY_FAILED)", "#DC2626", "Cần kiểm tra dịch vụ Ollama"),
        }
        state_label, state_color, state_desc = state_colors.get(
            rm.state, (f"⚪ {rm.state.value}", "#475569", "Trạng thái không xác định")
        )

        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        with col_r1:
            with st.container(border=True):
                st.markdown(
                    f'<div class="stat-card-label">Trạng Thái Hệ Thống</div>'
                    f'<div class="stat-card-value" style="color:{state_color}; font-size:1.05rem;">{state_label}</div>'
                    f'<div class="stat-card-caption">{state_desc}</div>',
                    unsafe_allow_html=True
                )

        with col_r2:
            with st.container(border=True):
                if vram_data["available"]:
                    vram_val = f"{vram_data['free_mb']:,.0f} MB Trống"
                    vram_sub = f"Đã dùng: {vram_data['used_mb']:,.0f} / {vram_data['total_mb']:,.0f} MB ({vram_data['used_pct']}%)"
                else:
                    vram_val = "N/A (Chỉ có CPU)"
                    vram_sub = "Không tìm thấy GPU NVIDIA CUDA"
                st.markdown(
                    f'<div class="stat-card-label">VRAM Động (GPU)</div>'
                    f'<div class="stat-card-value">{vram_val}</div>'
                    f'<div class="stat-card-caption">{vram_sub}</div>',
                    unsafe_allow_html=True
                )

        with col_r3:
            with st.container(border=True):
                if ram_data["total_mb"] > 0:
                    ram_val = f"{ram_data['free_mb'] / 1024:.1f} GB Trống"
                    ram_sub = f"Đã dùng: {ram_data['used_mb'] / 1024:.1f} / {ram_data['total_mb'] / 1024:.1f} GB ({ram_data['load_pct']}%)"
                else:
                    ram_val = "Đang đọc..."
                    ram_sub = "RAM hệ thống"
                st.markdown(
                    f'<div class="stat-card-label">RAM Hệ Thống</div>'
                    f'<div class="stat-card-value">{ram_val}</div>'
                    f'<div class="stat-card-caption">{ram_sub}</div>',
                    unsafe_allow_html=True
                )

        with col_r4:
            with st.container(border=True):
                st.markdown(
                    f'<div class="stat-card-label">CPU & PyTorch Threads</div>'
                    f'<div class="stat-card-value">{cpu_data["torch_threads"]} Luồng Torch</div>'
                    f'<div class="stat-card-caption">{cpu_data["logical_cores"]} logical cores (Giới hạn chống nghẽn)</div>',
                    unsafe_allow_html=True
                )

        # 2. Thông số phần cứng & Dịch vụ Runtime động (chỉ kiểm tra khi mở trang chẩn đoán)
        st.markdown("#### 2. Cấu Hình Phần Cứng & Dịch Vụ Runtime")
        hw_info = get_hardware_runtime_info()
        ollama_info = get_ollama_runtime_status(settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL)

        col_h1, col_h2, col_h3 = st.columns(3)
        with col_h1:
            with st.container(border=True):
                bge_active_dev = rm.model_manager.current_device.upper()
                st.markdown(
                    f'<div class="stat-card-label">Thiết Bị BGE-M3 Đang Chạy</div>'
                    f'<div class="stat-card-value">{bge_active_dev}</div>'
                    f'<div class="stat-card-caption">Chat: {settings.EMBEDDING_CHAT_DEVICE.upper()} | Batch Max: {settings.INDEXING_GPU_BATCH_SIZE if bge_active_dev == "CUDA" else settings.INDEXING_CPU_BATCH_SIZE}</div>',
                    unsafe_allow_html=True
                )

        with col_h2:
            with st.container(border=True):
                status_val_html = (
                    f'<div class="stat-card-value" style="color:#16A34A;">🟢 Trực tuyến</div>'
                    f'<div class="stat-card-caption">{settings.OLLAMA_BASE_URL}</div>'
                    if ollama_info["online"]
                    else
                    f'<div class="stat-card-value" style="color:#DC2626;">🔴 Ngoại tuyến</div>'
                    f'<div class="stat-card-caption">{ollama_info.get("error") or "Không thể kết nối"}</div>'
                )
                st.markdown(
                    f'<div class="stat-card-label">Dịch vụ Ollama Local</div>{status_val_html}',
                    unsafe_allow_html=True
                )

        with col_h3:
            with st.container(border=True):
                st.markdown(
                    f'<div class="stat-card-label">Thuật Toán RAG</div>'
                    f'<div class="stat-card-value">Hybrid RRF (k={settings.RRF_K})</div>'
                    f'<div class="stat-card-caption">BM25 Okapi + BGE-M3 (1024-d)</div>',
                    unsafe_allow_html=True
                )

        # 3. Phân biệt trạng thái Ollama Models
        st.markdown("#### 3. Trạng Thái Mô Hình LLM")

        col_m1, col_m2, col_m3 = st.columns(3)

        with col_m1:
            with st.container(border=True):
                st.markdown("**Mô hình được cấu hình (Configured):**")
                st.code(settings.OLLAMA_MODEL, language="text")
                st.caption(f"Host: {settings.OLLAMA_BASE_URL} | Nhiệt độ T: {settings.LLM_TEMPERATURE}")

        with col_m2:
            with st.container(border=True):
                st.markdown("**Mô hình đã cài đặt cục bộ (Installed):**")
                if ollama_info["online"] and ollama_info["installed_models"]:
                    st.code("\n".join(ollama_info["installed_models"]), language="text")
                elif ollama_info["online"]:
                    st.info("Chưa có model nào trong danh sách /api/tags.")
                else:
                    st.caption("Chưa thể kiểm tra do dịch vụ Ollama đang ngoại tuyến.")

        with col_m3:
            with st.container(border=True):
                st.markdown("**Mô hình đang nạp trong VRAM/RAM (Running):**")
                if ollama_info["online"] and ollama_info["running_models"]:
                    st.code("\n".join(ollama_info["running_models"]), language="text")
                elif ollama_info["online"]:
                    st.info("Đang ở trạng thái chờ (Chưa nạp model vào VRAM).")
                else:
                    st.caption("Chưa thể kiểm tra do dịch vụ Ollama đang ngoại tuyến.")

    # 3. Ngưỡng Relevance Gate & Inspector
    with st.container(border=True):
        st.markdown("#### 3. Cấu hình Ngưỡng Lọc Phù Hợp (Relevance Gate)")
        col_g1, col_g2, col_g3 = st.columns(3)
        col_g1.metric("Direct Match Threshold", f"≥ {settings.DIRECT_MATCH_RRF_THRESHOLD}")
        col_g2.metric("RAG Generation Threshold", f"≥ {settings.RAG_RRF_THRESHOLD}")
        col_g3.metric("Fallback Threshold", f"≥ {settings.FALLBACK_RRF_THRESHOLD}")

        st.markdown("---")
        st.markdown("#### 4. Cấu Hình Hiển Thị Kiểm Định")
        dev_mode_toggle = st.checkbox(
            "Hiển thị Bảng Phân Tích Kỹ Thuật (Inspector: RRF, PhoBERT, Latency) dưới câu trả lời tại Tab Tra Cứu",
            value=st.session_state.dev_mode,
            key="cb_dev_mode_toggle"
        )
        if dev_mode_toggle != st.session_state.dev_mode:
            st.session_state.dev_mode = dev_mode_toggle
            st.rerun()

    # 4. System Prompt thực tế (Read-only)
    with st.container(border=True):
        st.markdown("#### 5. System Prompt Cố Định (Chống Bịa Đặt & Bảo Toàn Cấu Trúc)")
        try:
            from src.llm.prompts import SYSTEM_PROMPT
            system_prompt_source = "src.llm.prompts.SYSTEM_PROMPT"
            system_prompt_val = SYSTEM_PROMPT
        except Exception as prompt_err:
            system_prompt_source = f"Lỗi đọc prompt: {prompt_err}"
            system_prompt_val = None

        st.caption(f"Nguồn xác thực: `{system_prompt_source}`")

        if system_prompt_val:
            st.text_area(
                label="System Prompt Read-only",
                value=system_prompt_val,
                height=200,
                disabled=True,
                label_visibility="collapsed",
                key="textarea_system_prompt_readonly"
            )
        else:
            st.error("Không thể đọc System Prompt từ module src.llm.prompts.")

    # 5. Nhật ký truy vấn (Audit Trace Logs)
    with st.container(border=True):
        st.markdown("#### 6. Nhật Ký Truy Vấn Thời Gian Thực (Audit Trace Logs)")
        st.caption("Lưu trữ chi tiết các lượt hỏi, intent, điểm số RRF và độ trễ để phục vụ kiểm toán:")

        if st.session_state.audit_logs:
            audit_table = []
            for log in reversed(st.session_state.audit_logs):
                audit_table.append({
                    "Thời gian": log.get("timestamp"),
                    "Câu hỏi": log.get("query"),
                    "Chế độ": log.get("mode"),
                    "Intent": log.get("intent") or "N/A",
                    "RRF Score": f"{log.get('rrf_score', 0.0):.4f}",
                    "Độ trễ": f"{log.get('latency_ms', 0.0):.1f} ms",
                    "Mã bản ghi": log.get("record_id") or "N/A",
                })
            st.dataframe(audit_table, use_container_width=True)

            col_a1, col_a2 = st.columns([1, 1])
            with col_a1:
                st.download_button(
                    label="📥 Tải Nhật Ký Audit (JSON)",
                    data=json.dumps(st.session_state.audit_logs, ensure_ascii=False, indent=2),
                    file_name="chatbox2_audit_log.json",
                    mime="application/json",
                    use_container_width=True,
                    key="btn_download_audit_json"
                )
            with col_a2:
                if st.button("🗑️ Xóa Lịch Sử Nhật Ký", key="btn_clear_audit_logs", use_container_width=True):
                    st.session_state.audit_logs = []
                    st.toast("Đã xóa toàn bộ nhật ký kiểm định.", icon="🧹")
                    st.rerun()
        else:
            st.info("Chưa có lượt truy vấn nào trong phiên làm việc hiện tại.")

        st.markdown("---")
        # Nhật ký kiểm toán bảo mật quản trị (Admin Audit Logs từ cơ sở dữ liệu)
        from src.data.audit_repository import AuditRepository
        from src.ui.audit_view import render_admin_audit_logs
        render_admin_audit_logs(AuditRepository(), current_user)


elif st.session_state.nav_page == "👤 Thông tin cá nhân":
    # --------------------------------------------------------------------------
    # TRANG HỒ SƠ CÁ NHÂN & ĐỔI MẬT KHẨU
    # --------------------------------------------------------------------------
    col_ret_1, col_ret_2 = st.columns([1, 5])
    with col_ret_1:
        if st.button("← Trò chuyện", key="btn_ret_from_profile"):
            st.session_state.nav_page = "💬 Tra cứu từ vựng"
            st.rerun()

    from src.ui.profile_view import render_profile_view
    render_profile_view(auth_service, current_user)

