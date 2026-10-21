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
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

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

# Ép buộc Streamlit Theme luôn ở chế độ Light Theme (chống browser/OS dark mode làm đen canvas st.dataframe và checkbox)
os.environ["STREAMLIT_THEME_BASE"] = "light"
os.environ["STREAMLIT_THEME_PRIMARY_COLOR"] = "#2563EB"
os.environ["STREAMLIT_THEME_BACKGROUND_COLOR"] = "#FFFFFF"
os.environ["STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR"] = "#F8FAFC"
os.environ["STREAMLIT_THEME_TEXT_COLOR"] = "#0F172A"

import requests
import streamlit as st

# Cho phép chạy trực tiếp bằng lệnh `python app.py` hoặc nút Run trong VS Code
if __name__ == "__main__":
    if not st.runtime.exists():
        from streamlit.web import cli as stcli
        sys.argv = ["streamlit", "run", __file__]
        sys.exit(stcli.main())

import importlib
# Tự động nạp lại các module lõi nếu tiến trình Streamlit đang chạy từ trước khi cập nhật mã nguồn
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
from src.chat.engine import ChatEngine
from src.core.models import ChatResponse
from src.data.batch_ingestion import BatchIngestionManager, BatchStatus, FileStatus
from src.data.loaders.sqlite_loader import (
    SQLiteLoader,
    SQLiteMappingConfig,
    SQLiteMappingMode,
    SQLiteSchemaInfo,
)
from src.ui.theme import CUSTOM_CSS

logger = logging.getLogger(__name__)

# Đọc an toàn System Prompt thực tế từ src.llm.prompts
try:
    from src.llm.prompts import SYSTEM_PROMPT
    SYSTEM_PROMPT_SOURCE = "src.llm.prompts.SYSTEM_PROMPT"
except Exception as prompt_err:
    SYSTEM_PROMPT = None
    SYSTEM_PROMPT_SOURCE = f"Lỗi đọc prompt: {prompt_err}"

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

# Áp dụng CSS Theme đồng bộ
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)




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


def inspect_storage_metrics(engine: ChatEngine) -> Dict[str, Any]:
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


# --- KHỞI TẠO SINGLETON CHAT ENGINE & BATCH MANAGER ---

@st.cache_resource(show_spinner="Đang khởi tạo các chỉ mục tri thức và mô hình...")
def get_chatbot_engine() -> ChatEngine:
    """Tạo singleton instance của ChatEngine và làm nóng các chỉ mục."""
    eng = ChatEngine()
    eng.warm_up()
    return eng


engine = get_chatbot_engine()
batch_manager = BatchIngestionManager()

# --- KHỞI TẠO SESSION STATE CỐT LÕI ---
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

# Lấy trạng thái runtime
ollama_info = get_ollama_runtime_status(settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL)
kb_records_count = len(engine.records) if hasattr(engine, "records") and engine.records else 0


# ==============================================================================
# SIDEBAR BÊN TRÁI: LOGO, NÚT CUỘC TRÒ CHUYỆN MỚI, ĐIỀU HƯỚNG
# ==============================================================================
with st.sidebar:
    # 1. Logo & Tên ứng dụng
    st.markdown(
        """
        <div class="sidebar-header-box">
            <span class="sidebar-app-icon">🤖</span>
            <span class="sidebar-app-title">Chatbox 2.0</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 2. Nút '+ Cuộc trò chuyện mới'
    if st.button("➕ Cuộc trò chuyện mới", key="btn_sidebar_new_chat", use_container_width=True):
        st.session_state.messages = []
        if hasattr(engine, "tracker") and hasattr(engine.tracker, "clear"):
            engine.tracker.clear()
        st.session_state.status = "Sẵn sàng!"
        st.session_state.is_processing = False
        st.session_state.nav_page = "💬 Tra cứu từ vựng"
        st.toast("Đã bắt đầu cuộc trò chuyện mới.", icon="✨")
        st.rerun()

    # Đường phân cách
    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

    # 3. Mục ĐIỀU HƯỚNG
    st.markdown('<div class="sidebar-section-title">ĐIỀU HƯỚNG</div>', unsafe_allow_html=True)
    
    nav_options = [
        "💬 Tra cứu từ vựng",
        "🗄️ Quản lý dữ liệu",
        "📈 Chẩn đoán"
    ]
    
    current_index = nav_options.index(st.session_state.nav_page) if st.session_state.nav_page in nav_options else 0
    selected_nav = st.radio(
        label="Điều hướng trang",
        options=nav_options,
        index=current_index,
        key="radio_nav_sidebar",
        label_visibility="collapsed"
    )
    if selected_nav != st.session_state.nav_page:
        st.session_state.nav_page = selected_nav
        st.rerun()

    # 4. Trạng thái Ollama ở chân sidebar
    ollama_class = "online" if ollama_info["online"] else "offline"
    ollama_text = "● Ollama sẵn sàng" if ollama_info["online"] else "● Ollama ngoại tuyến"
    st.markdown(
        f'<div class="sidebar-footer-status {ollama_class}">{ollama_text}</div>',
        unsafe_allow_html=True
    )


# ==============================================================================
# KHUNG CHÍNH (MAIN AREA)
# ==============================================================================

# ==============================================================================
# CÁC HÀM RENDER & XỬ LÝ HỘI THOẠI CHUẨN MODERN STREAMLIT CHAT UI
# ==============================================================================

def render_user_turn(content: str) -> None:
    """Hiển thị lượt tin nhắn của người dùng: căn phải, icon người dùng có sẵn, bong bóng xám nhạt."""
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


def render_bot_card_header() -> None:
    """Hiển thị tiêu đề thẻ Card của Chatbox kèm biểu tượng robot."""
    st.markdown(
        """
        <div class="bot-card-header">
            <span class="bot-card-icon">🤖</span>
            <span class="bot-card-title">Chatbox</span>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_provenance_and_inspector(meta: Optional[ChatResponse]) -> None:
    """Hiển thị thông tin xuất xứ dữ liệu (Provenance) và bảng kỹ thuật (Inspector)."""
    if meta is None:
        return

    source_file = getattr(meta, "source", None)
    rec_id = getattr(meta, "record_id", None)
    word_val = getattr(meta, "word", None)
    sheet_val = None

    if getattr(meta, "candidates", None) and len(meta.candidates) > 0:
        top_candidate = meta.candidates[0].record
        if not source_file:
            source_file = getattr(top_candidate, "source", None) or getattr(top_candidate, "source_file", None)
        if not rec_id:
            rec_id = getattr(top_candidate, "record_id", None) or getattr(top_candidate, "id", None)
        if not word_val:
            word_val = getattr(top_candidate, "word", None)
        sheet_val = getattr(top_candidate, "sheet", None)

    has_provenance = any([rec_id, source_file, word_val, sheet_val])
    if has_provenance:
        with st.expander("📄 Nguồn dữ liệu · Mở rộng", expanded=False):
            prov_html = []
            if rec_id:
                prov_html.append(f'<span class="source-badge">Mã: <b>{html.escape(str(rec_id))}</b></span>')
            if word_val:
                prov_html.append(f'<span class="source-badge">Từ: <b>{html.escape(str(word_val))}</b></span>')
            if source_file:
                prov_html.append(f'<span class="source-badge">Tệp: <b>{html.escape(str(source_file))}</b></span>')
            if sheet_val:
                prov_html.append(f'<span class="source-badge">Sheet/Phần: <b>{html.escape(str(sheet_val))}</b></span>')
            st.markdown("".join(prov_html), unsafe_allow_html=True)

    if st.session_state.get("dev_mode", False):
        with st.expander("🔬 Bảng phân tích kỹ thuật (Inspector)", expanded=False):
            ic1, ic2, ic3, ic4 = st.columns(4)
            ic1.metric("Response Mode", str(getattr(meta, "mode", "N/A")))
            ic2.metric("PhoBERT Intent", str(getattr(meta, "intent", "N/A") or "N/A"))
            ic3.metric("RRF Score", f"{getattr(meta, 'rrf_score', 0.0):.4f}")
            ic4.metric("Độ trễ", f"{getattr(meta, 'latency_ms', 0.0):.1f} ms")


def render_assistant_turn(content: str, meta: Optional[ChatResponse] = None) -> None:
    """Hiển thị lượt tin nhắn chatbot hoàn chỉnh trong lịch sử hội thoại."""
    with st.chat_message("assistant", avatar=BOT_AVATAR):
        col_bot, col_spacer = st.columns([4, 1])
        with col_bot:
            with st.container(border=True):
                render_bot_card_header()
                st.markdown(content)
                render_provenance_and_inspector(meta)


def process_user_query(
    clean_input: str,
    chat_engine: ChatEngine,
    messages_container=None,
    empty_state_placeholder=None,
) -> Optional[ChatResponse]:
    """Quy trình xử lý một câu hỏi của người dùng chuẩn luồng hiện đại:
    1. Cập nhật câu hỏi vào st.session_state.messages ngay lập tức.
    2. Render bubble người dùng ngay lập tức trên UI trước khi bắt đầu backend.
    3. Render bubble assistant cùng placeholder trạng thái 'Đang phân tích câu hỏi & tìm kiếm dữ liệu...'.
    4. Gọi ChatEngine.ask_stream() để sinh câu trả lời theo luồng (streaming).
    5. Cập nhật các chunk phản hồi thay thế placeholder trạng thái.
    6. Lưu câu trả lời hoàn chỉnh cùng metadata vào st.session_state.messages.
    7. Ghi nhận nhật ký kiểm toán (audit log).
    """
    if not clean_input:
        return None

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
                col_bot, col_spacer = st.columns([4, 1])
                with col_bot:
                    with st.container(border=True):
                        render_bot_card_header()

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
                                for token, meta in chat_engine.ask_stream(clean_input):
                                    if meta is not None:
                                        response_holder["meta"] = meta
                                    if token:
                                        if first_chunk:
                                            status_placeholder.empty()
                                            first_chunk = False
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

                        # Render nguồn dữ liệu và inspector
                        render_provenance_and_inspector(final_meta)

        # Bước 4: Lưu câu trả lời hoàn chỉnh vào session state
        st.session_state.messages.append({
            "role": "assistant",
            "content": persisted_answer,
            "meta": final_meta
        })
        st.session_state.status = "Hoàn tất!"

        # Bước 5: Ghi audit log
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


if st.session_state.nav_page == "💬 Tra cứu từ vựng":
    # --------------------------------------------------------------------------
    # TRANG 1: 💬 TRA CỨU TỪ VỰNG (MAIN CHAT VIEW)
    # --------------------------------------------------------------------------

    # 1. Header Khung Chat: Tiêu đề + Badge 'Local' + Trạng thái thu gọn
    st.markdown(
        f"""
        <div class="chat-top-bar">
            <div class="chat-top-left">
                <span class="chat-view-title">Tra cứu từ vựng</span>
                <span class="chat-local-pill">Local</span>
            </div>
            <div class="chat-top-right">
                <span class="status-dot {ollama_class}">{ollama_text}</span>
                <span>• Kho tri thức: {kb_records_count:,} bản ghi</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 2. Vùng hiển thị tin nhắn (cuộn tự nhiên theo trình duyệt, không chia 2 thanh cuộn)
    messages_container = st.container()

    with messages_container:
        empty_state_placeholder = st.empty()
        if not st.session_state.messages:
            # Màn hình rỗng / Lời chào ban đầu (Empty State chuẩn Visual Reference)
            with empty_state_placeholder.container():
                st.markdown(
                    """
                    <div class="chat-empty-state-box">
                        <div class="chat-empty-icon">🗨️</div>
                        <div class="chat-empty-title">Bạn muốn tra cứu từ nào?</div>
                        <div class="chat-empty-subtitle">Nhập từ tiếng Anh hoặc câu hỏi bằng tiếng Việt.</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            for idx, msg in enumerate(st.session_state.messages):
                role = msg.get("role", "assistant")
                content = msg.get("content", "")
                meta: Optional[ChatResponse] = msg.get("meta")

                if role == "user":
                    render_user_turn(content)
                else:
                    render_assistant_turn(content, meta)

    # Dòng trạng thái chân khung chat
    st.markdown(
        f"""
        <div class="chat-bottom-status-line">
            <span class="status-dot {ollama_class}">{ollama_text}</span>
            <span>Chatbox 2.0 chạy cục bộ trên máy tính • Kho tri thức: {kb_records_count:,} bản ghi</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 3. Ô nhập câu hỏi st.chat_input (nằm ở đáy vùng chính qua API chính thức của Streamlit)
    user_query = st.chat_input("Nhập từ vựng hoặc câu hỏi tiếng Việt...")
    if user_query:
        clean_input = user_query.strip()
        if clean_input and not st.session_state.get("is_processing", False):
            process_user_query(
                clean_input=clean_input,
                chat_engine=engine,
                messages_container=messages_container,
                empty_state_placeholder=empty_state_placeholder,
            )


elif st.session_state.nav_page == "🗄️ Quản lý dữ liệu":
    # --------------------------------------------------------------------------
    # TRANG 2: 🗄️ QUẢN LÝ DỮ LIỆU (KNOWLEDGE BASE MANAGEMENT)
    # Lỗi D: Thay thế thẻ div panel-card bằng st.container(border=True)
    # --------------------------------------------------------------------------
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
                seen_upload_hashes: Dict[str, Path] = {}

                for uf in uploaded_batch_files:
                    content_bytes = uf.getvalue()
                    import hashlib
                    uf_hash = hashlib.sha256(content_bytes).hexdigest()

                    # Lưu trữ an toàn, tránh tạo thêm bản sao vật lý dư thừa
                    if uf_hash in seen_upload_hashes:
                        # Trùng nội dung với tệp khác trong cùng đợt: tạo bản sao tạm để phân tích
                        tmp_name = f"tmp_{uuid4().hex[:8]}_{uf.name}"
                        target_path = settings.RAW_DATA_DIR / tmp_name
                    elif not is_replace_mode and batch_manager.is_duplicate_file(uf_hash):
                        # Trùng nội dung với tệp đã có trong manifest: tạo bản sao tạm để phân tích
                        tmp_name = f"tmp_{uuid4().hex[:8]}_{uf.name}"
                        target_path = settings.RAW_DATA_DIR / tmp_name
                    else:
                        # Tệp mới: lưu với tên gốc nếu chưa tồn tại
                        candidate_path = settings.RAW_DATA_DIR / uf.name
                        if candidate_path.exists():
                            target_path = settings.RAW_DATA_DIR / f"raw_{uf_hash[:8]}_{uf.name}"
                        else:
                            target_path = candidate_path

                    with open(target_path, "wb") as f:
                        f.write(content_bytes)
                    saved_paths.append(target_path)
                    if uf_hash not in seen_upload_hashes:
                        seen_upload_hashes[uf_hash] = target_path

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


elif st.session_state.nav_page == "📈 Chẩn đoán":
    # --------------------------------------------------------------------------
    # TRANG 3: 📈 CHẨN ĐOÁN & KIỂM ĐỊNH (DIAGNOSTICS & AUDIT)
    # Lỗi D: Thay thế thẻ div panel-card bằng st.container(border=True)
    # --------------------------------------------------------------------------
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

        # 2. Thông số phần cứng & Dịch vụ Runtime động
        st.markdown("#### 2. Cấu Hình Phần Cứng & Dịch Vụ Runtime")
        hw_info = get_hardware_runtime_info()

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
        st.caption(f"Nguồn xác thực: `{SYSTEM_PROMPT_SOURCE}`")

        if SYSTEM_PROMPT:
            st.text_area(
                label="System Prompt Read-only",
                value=SYSTEM_PROMPT,
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
