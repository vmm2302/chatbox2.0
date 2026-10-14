"""Giao diện Web Chatbox 2.0 phát triển trên Streamlit.

Hệ thống tra cứu từ vựng tiếng Anh bằng tiếng Việt:
- Tab 1 (💬 Tra Cứu Từ Vựng): Giao diện 1 cột trung tâm tối giản, lịch sử hội thoại, expander nguồn dữ liệu thật, nút Cuộc trò chuyện mới.
- Tab 2 (📁 Quản Lý Dữ Liệu): Nạp đa tệp (8 định dạng), phân tách ADD/REPLACE kèm xác nhận an toàn, thống kê lưu trữ độc lập (JSONL, ChromaDB, BM25).
- Tab 3 (🛠️ Chẩn Đoán & Kiểm Định): Thông số động GPU/CUDA, phân biệt model cấu hình/đã cài/đang nạp, System Prompt read-only, công tắc Inspector, nhật ký audit.
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

import requests
import streamlit as st

# Cho phép chạy trực tiếp bằng lệnh `python app.py` hoặc nút Run trong VS Code
if __name__ == "__main__":
    if not st.runtime.exists():
        from streamlit.web import cli as stcli
        sys.argv = ["streamlit", "run", __file__]
        sys.exit(stcli.main())

from config.settings import settings
from src.chat.engine import ChatEngine
from src.core.models import ChatResponse
from src.data.batch_ingestion import BatchIngestionManager, BatchStatus, FileStatus
from src.ui.theme import CUSTOM_CSS

logger = logging.getLogger(__name__)

# Đọc an toàn System Prompt thực tế từ src.llm.prompts
try:
    from src.llm.prompts import SYSTEM_PROMPT
    SYSTEM_PROMPT_SOURCE = "src.llm.prompts.SYSTEM_PROMPT"
except Exception as prompt_err:
    SYSTEM_PROMPT = None
    SYSTEM_PROMPT_SOURCE = f"Lỗi đọc prompt: {prompt_err}"

# Đường dẫn Avatar và dữ liệu base64 đồng bộ từ assets/
user_img_path = project_root / "assets" / "user.png"
bot_img_path = project_root / "assets" / "bot.png"

USER_AVATAR = str(user_img_path) if user_img_path.exists() else "👤"
BOT_AVATAR = str(bot_img_path) if bot_img_path.exists() else "🤖"

USER_B64 = base64.b64encode(user_img_path.read_bytes()).decode("ascii") if user_img_path.exists() else ""
BOT_B64 = base64.b64encode(bot_img_path.read_bytes()).decode("ascii") if bot_img_path.exists() else ""

# Cấu hình trang Streamlit
st.set_page_config(
    page_title="Chatbox 2.0 - Tra Cứu Từ Vựng Tiếng Anh",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
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
        # 1. Kiểm tra /api/tags để lấy danh sách model đã cài đặt
        tags_resp = requests.get(f"{clean_url}/api/tags", timeout=1.5)
        if tags_resp.status_code == 200:
            status["online"] = True
            tags_data = tags_resp.json()
            models_list = tags_data.get("models", [])
            status["installed_models"] = [m.get("name") for m in models_list if m.get("name")]

            # 2. Kiểm tra /api/ps để lấy model đang nạp vào VRAM/RAM
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
            coll = engine.bge_retriever.collection
            if coll is not None:
                results["chroma_count"] = coll.count()
            else:
                import chromadb
                client = chromadb.PersistentClient(path=str(settings.CHROMA_DIR))
                coll = client.get_collection(name=settings.CHROMA_COLLECTION_NAME)
                results["chroma_count"] = coll.count()
        else:
            results["chroma_error"] = "Không tìm thấy bge_retriever"
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


# --- HEADER VÀ THANH TRẠNG THÁI CHUNG ---
ollama_info = get_ollama_runtime_status(settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL)
kb_records_count = len(engine.records) if hasattr(engine, "records") and engine.records else 0

st.markdown('<div class="app-header-container">', unsafe_allow_html=True)
st.markdown('<div class="app-title">Chatbox 2.0 🤖</div>', unsafe_allow_html=True)
st.markdown('<div class="app-subtitle">Hệ thống tra cứu từ vựng tiếng Anh theo ngữ cảnh & chuẩn CEFR</div>', unsafe_allow_html=True)

ollama_badge_class = "online" if ollama_info["online"] else "offline"
ollama_badge_text = f"🟢 Ollama: {ollama_info['configured_model']}" if ollama_info["online"] else "🔴 Ollama: Ngoại tuyến"

st.markdown(
    f"""
    <div class="header-badges">
        <span class="status-badge {ollama_badge_class}">{ollama_badge_text}</span>
        <span class="status-badge">📚 Kho tri thức: {kb_records_count:,} bản ghi</span>
    </div>
    """,
    unsafe_allow_html=True
)
st.markdown('</div>', unsafe_allow_html=True)


# --- BỐ CỤC 3 TAB CHUYÊN BIỆT ---
tab_chat, tab_knowledge, tab_diagnostics = st.tabs([
    "💬 Tra Cứu Từ Vựng",
    "📁 Quản Lý Dữ Liệu",
    "🛠️ Chẩn Đoán & Kiểm Định"
])


# ==============================================================================
# TAB 1: 💬 TRA CỨU TỪ VỰNG (MÀN HÌNH CHÍNH)
# ==============================================================================
with tab_chat:
    # 1. Thanh điều khiển: Nút "Cuộc trò chuyện mới"
    col_t1, col_t2 = st.columns([6, 2])
    with col_t2:
        if st.button("➕ Cuộc trò chuyện mới", key="btn_new_chat", use_container_width=True):
            st.session_state.messages = []
            if hasattr(engine, "tracker") and hasattr(engine.tracker, "clear"):
                engine.tracker.clear()
            st.session_state.status = "Sẵn sàng!"
            st.toast("Đã bắt đầu cuộc trò chuyện mới.", icon="✨")
            st.rerun()

    # 2. Khung hiển thị tin nhắn hội thoại
    chat_container = st.container()
    with chat_container:
        if not st.session_state.messages:
            # Trạng thái rỗng: Lời chào tiếng Việt trang nhã, KHÔNG có thẻ gợi ý nhanh
            st.markdown(
                """
                <div class="welcome-card">
                    <div class="welcome-title">Chào mừng bạn đến với Chatbox 2.0! 👋</div>
                    <div class="welcome-text">
                        Hệ thống hỗ trợ tra cứu định nghĩa, phiên âm, từ loại, cấp độ CEFR và câu ví dụ của từ vựng tiếng Anh bằng câu hỏi tiếng Việt tự nhiên.<br/>
                        Hãy nhập từ vựng tiếng Anh hoặc câu hỏi của bạn vào ô bên dưới để bắt đầu tra cứu.
                    </div>
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
                    st.markdown(
                        f"""
                        <div class="user-msg-wrapper">
                            <div class="user-bubble-box">{html.escape(content)}</div>
                            <img class="user-avatar-img" src="data:image/png;base64,{USER_B64}" alt="User" />
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    # Tin nhắn Bot
                    st.markdown(
                        f"""
                        <div class="bot-msg-wrapper">
                            <img class="bot-avatar-img" src="data:image/png;base64,{BOT_B64}" alt="Bot" />
                            <div class="bot-bubble-box">
                        """,
                        unsafe_allow_html=True
                    )
                    # Render Markdown nội dung trả lời (bảo toàn định dạng phân dòng, in đậm, danh sách)
                    st.markdown(content)

                    # Hiển thị Nguồn dữ liệu (Provenance) - Chỉ hiển thị metadata có thật
                    if meta is not None:
                        # Trích xuất metadata thực tế từ response hoặc candidate đầu tiên
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

                        # Chỉ hiển thị Expander Nguồn dữ liệu khi có ít nhất một thông tin metadata có thật
                        has_provenance = any([rec_id, source_file, word_val, sheet_val])
                        if has_provenance:
                            with st.expander("📄 Nguồn dữ liệu trích xuất", expanded=False):
                                prov_html = []
                                if rec_id:
                                    prov_html.append(f'<span class="source-badge">Mã bản ghi: <b>{html.escape(str(rec_id))}</b></span>')
                                if word_val:
                                    prov_html.append(f'<span class="source-badge">Từ vựng: <b>{html.escape(str(word_val))}</b></span>')
                                if source_file:
                                    prov_html.append(f'<span class="source-badge">Tệp nguồn: <b>{html.escape(str(source_file))}</b></span>')
                                if sheet_val:
                                    prov_html.append(f'<span class="source-badge">Sheet/Phần: <b>{html.escape(str(sheet_val))}</b></span>')

                                st.markdown("".join(prov_html), unsafe_allow_html=True)

                        # Bảng Inspector Kỹ thuật: Chỉ hiển thị khi người dùng bật tùy chọn ở Tab Chẩn đoán
                        if st.session_state.dev_mode:
                            with st.expander("🔬 Bảng phân tích kỹ thuật (Inspector)", expanded=False):
                                ic1, ic2, ic3, ic4 = st.columns(4)
                                ic1.metric("Response Mode", str(getattr(meta, "mode", "N/A")))
                                ic2.metric("PhoBERT Intent", str(getattr(meta, "intent", "N/A") or "N/A"))
                                ic3.metric("RRF Score", f"{getattr(meta, 'rrf_score', 0.0):.4f}")
                                ic4.metric("Độ trễ", f"{getattr(meta, 'latency_ms', 0.0):.1f} ms")

                    st.markdown('</div></div>', unsafe_allow_html=True)

    # 3. Ô nhập câu hỏi người dùng
    user_query = st.chat_input("Nhập từ vựng tiếng Anh hoặc câu hỏi bằng tiếng Việt...")
    if user_query:
        clean_input = user_query.strip()
        if clean_input:
            # Lưu tin nhắn người dùng
            st.session_state.messages.append({
                "role": "user",
                "content": clean_input
            })
            st.session_state.status = "Đang xử lý..."

            # Gọi ChatEngine xử lý câu hỏi với xử lý ngoại lệ an toàn
            try:
                response = engine.ask(clean_input)
            except Exception as ask_err:
                logger.error("Lỗi khi xử lý truy vấn: %s", ask_err, exc_info=True)
                response = ChatResponse(
                    answer=(
                        f"⚠️ **Không thể kết nối hoặc xử lý câu trả lời từ mô hình.**\n\n"
                        f"- Chi tiết lỗi: `{ask_err}`\n"
                        f"- Vui lòng kiểm tra dịch vụ Ollama cục bộ ({settings.OLLAMA_BASE_URL}) hoặc thử lại sau."
                    ),
                    mode="ERROR",
                    latency_ms=0.0
                )

            # Lưu câu trả lời bot
            st.session_state.messages.append({
                "role": "assistant",
                "content": response.answer,
                "meta": response
            })
            st.session_state.status = "Hoàn tất!"

            # Ghi nhật ký vào audit log
            active_word_val = getattr(engine.tracker, "active_word", None) if hasattr(engine, "tracker") else None
            st.session_state.audit_logs.append({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "query": clean_input,
                "mode": str(getattr(response, "mode", "UNKNOWN")),
                "intent": getattr(response, "intent", None),
                "active_word": active_word_val,
                "record_id": getattr(response, "record_id", None),
                "rrf_score": getattr(response, "rrf_score", 0.0),
                "latency_ms": getattr(response, "latency_ms", 0.0),
                "answer": response.answer
            })
            st.rerun()


# ==============================================================================
# TAB 2: 📁 QUẢN LÝ DỮ LIỆU (KNOWLEDGE BASE MANAGEMENT)
# ==============================================================================
with tab_knowledge:
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.markdown('<div class="panel-card-header">📁 Quản Trị & Cập Nhật Kho Tri Thức</div>', unsafe_allow_html=True)
    st.markdown(
        "Hỗ trợ tải lên cùng lúc nhiều tệp dữ liệu thuộc **8 định dạng tài liệu** "
        "để tự động trích xuất, khử trùng lặp và cập nhật cơ sở dữ liệu vector mà không cần khởi động lại ứng dụng."
    )

    # 1. Khung Uploader Đa Tệp
    uploaded_batch_files = st.file_uploader(
        label="Chọn một hoặc nhiều tệp để nạp vào Knowledge Base:",
        type=["pdf", "docx", "txt", "csv", "xlsx", "json", "jsonl", "md"],
        accept_multiple_files=True,
        help="Hỗ trợ: PDF, Word (.docx), Excel (.xlsx), CSV (.csv), JSON (.json, .jsonl), Text (.txt, .md).",
        key="uploader_batch_multi_files"
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

        # Nút bấm bắt đầu xử lý
        if st.button(
            "🚀 Bắt Đầu Xử Lý Batch Tệp",
            key="btn_process_batch_all",
            type="primary",
            disabled=not can_proceed,
            use_container_width=True
        ):
            settings.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
            saved_paths: List[Path] = []
            for uf in uploaded_batch_files:
                safe_name = f"batch_{uuid4().hex[:8]}_{uf.name}"
                target_path = settings.RAW_DATA_DIR / safe_name
                with open(target_path, "wb") as f:
                    f.write(uf.getbuffer())
                saved_paths.append(target_path)

            progress_bar = st.progress(0, text="Đang khởi tạo tiến trình nạp...")

            def ui_batch_callback(msg: str, pct: float, current_res: Optional[Any] = None):
                clamped_pct = max(0.0, min(1.0, float(pct)))
                progress_bar.progress(int(clamped_pct * 100), text=msg)

            selected_mode_str = "replace" if is_replace_mode else "add"

            try:
                # Thực thi Batch Ingestion
                report = batch_manager.ingest_batch(
                    files=saved_paths,
                    mode=selected_mode_str,
                    progress_callback=ui_batch_callback
                )
                st.session_state.batch_report = report

                # Kiểm tra trạng thái báo cáo thực tế: Phân biệt SUCCESS, PARTIAL_SUCCESS và FAILED
                b_status = getattr(report, "batch_status", BatchStatus.FAILED)
                status_val = b_status.value if hasattr(b_status, "value") else str(b_status)

                if status_val == BatchStatus.SUCCESS.value:
                    # Nạp lại dữ liệu vào bộ nhớ ChatEngine
                    new_records = batch_manager.loader.load_from_jsonl()
                    engine.update_knowledge_base(new_records)
                    progress_bar.progress(100, text="Hoàn tất xử lý batch thành công!")
                    st.success("Đã hoàn tất xử lý và cập nhật kho tri thức thành công!")
                    st.toast("Hoàn tất xử lý Batch!", icon="🎉")
                elif status_val == BatchStatus.PARTIAL_SUCCESS.value:
                    new_records = batch_manager.loader.load_from_jsonl()
                    engine.update_knowledge_base(new_records)
                    progress_bar.progress(100, text="Xử lý hoàn tất một phần (Có tệp bị bỏ qua hoặc lỗi).")
                    st.warning("Hoàn tất xử lý một phần: Một số tệp đã được thêm, một số tệp bị bỏ qua hoặc lỗi.")
                    st.toast("Xử lý hoàn tất một phần!", icon="⚠️")
                else:
                    # Trạng thái FAILED
                    progress_bar.progress(100, text="Xử lý batch thất bại. Dữ liệu cũ được bảo toàn.")
                    st.error(
                        "Batch ingestion thất bại hoặc thao tác thay thế bị hủy bỏ. "
                        "Kho tri thức cũ được bảo toàn nguyên vẹn."
                    )
            except Exception as batch_err:
                logger.error("Lỗi trong quá trình thực thi batch ingestion: %s", batch_err, exc_info=True)
                st.error(f"Đã xảy ra sự cố nghiêm trọng khi nạp dữ liệu: {batch_err}")

            st.rerun()

    # 2. Báo cáo kết quả xử lý Batch gần nhất
    report = st.session_state.batch_report
    if report:
        st.markdown("---")
        st.subheader("📊 Báo Cáo Xử Lý Batch Gần Nhất")
        b_status = getattr(report, "batch_status", BatchStatus.FAILED)
        status_val = b_status.value if hasattr(b_status, "value") else str(b_status)

        col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
        col_s1.metric("Tổng số tệp", report.total_files)
        col_s2.metric("Thành công", report.success_count)
        col_s3.metric("Bỏ qua", report.skipped_count)
        col_s4.metric("Thất bại", report.failed_count)
        col_s5.metric("Trạng thái", status_val)

        # Chi tiết từng tệp
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
    st.markdown("---")
    st.subheader("📦 Trạng Thái Lưu Trữ & Chỉ Mục Độc Lập")
    st.caption("Các tầng lưu trữ và chỉ mục được quản lý riêng biệt, phản ánh số liệu thực tế:")

    storage_stats = inspect_storage_metrics(engine)
    col_k1, col_k2, col_k3, col_k4 = st.columns(4)

    with col_k1:
        st.markdown('<div class="metric-box">', unsafe_allow_html=True)
        st.markdown('<div class="metric-label">Tệp JSONL Trên Đĩa</div>', unsafe_allow_html=True)
        if storage_stats["jsonl_disk_count"] is not None:
            st.markdown(f'<div class="metric-value">{storage_stats["jsonl_disk_count"]:,} dòng</div>', unsafe_allow_html=True)
            st.markdown('<div class="metric-caption">data/processed/qa_records.jsonl</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="metric-value" style="color:#DC2626;font-size:0.9rem;">⚠️ {storage_stats["jsonl_disk_error"]}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_k2:
        st.markdown('<div class="metric-box">', unsafe_allow_html=True)
        st.markdown('<div class="metric-label">Bộ Nhớ ChatEngine</div>', unsafe_allow_html=True)
        if storage_stats["engine_records_count"] is not None:
            st.markdown(f'<div class="metric-value">{storage_stats["engine_records_count"]:,} bản ghi</div>', unsafe_allow_html=True)
            st.markdown('<div class="metric-caption">QARecord nạp trong RAM</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="metric-value" style="color:#DC2626;font-size:0.9rem;">⚠️ {storage_stats["engine_records_error"]}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_k3:
        st.markdown('<div class="metric-box">', unsafe_allow_html=True)
        st.markdown('<div class="metric-label">ChromaDB Vector</div>', unsafe_allow_html=True)
        if storage_stats["chroma_count"] is not None:
            st.markdown(f'<div class="metric-value">{storage_stats["chroma_count"]:,} vectors</div>', unsafe_allow_html=True)
            st.markdown('<div class="metric-caption">Chỉ mục BGE-M3 (1024-d)</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="metric-value" style="color:#DC2626;font-size:0.9rem;">⚠️ {storage_stats["chroma_error"]}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_k4:
        st.markdown('<div class="metric-box">', unsafe_allow_html=True)
        st.markdown('<div class="metric-label">BM25 Lexical Index</div>', unsafe_allow_html=True)
        if storage_stats["bm25_count"] is not None:
            st.markdown(f'<div class="metric-value">{storage_stats["bm25_count"]:,} mục</div>', unsafe_allow_html=True)
            st.markdown('<div class="metric-caption">Inverted Index từ khóa</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="metric-value" style="color:#DC2626;font-size:0.9rem;">⚠️ {storage_stats["bm25_error"]}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Đánh giá trạng thái sẵn sàng
    indices_ready = (
        storage_stats["engine_records_count"] is not None and storage_stats["engine_records_count"] > 0 and
        storage_stats["chroma_count"] is not None and storage_stats["chroma_count"] > 0 and
        storage_stats["bm25_count"] is not None and storage_stats["bm25_count"] > 0
    )
    if indices_ready:
        st.success("🟢 Toàn bộ 3 chỉ mục (JSONL, ChromaDB, BM25) đã được tải và sẵn sàng phục vụ tra cứu.")
    else:
        st.warning("⚠️ Một hoặc nhiều tầng chỉ mục chưa sẵn sàng hoặc rỗng. Vui lòng kiểm tra lại dữ liệu.")

    st.caption(
        "💡 *Lưu ý kỹ thuật: Số lượng bản ghi JSONL, BM25 và ChromaDB vector được quản lý độc lập theo cơ chế "
        "khử trùng lặp và chunking của từng tầng lưu trữ và không nhất thiết phải có tỷ lệ 1:1.*"
    )

    # 4. Danh sách các nguồn dữ liệu đang hoạt động (Active Sources)
    active_sources = batch_manager.get_active_sources()
    if active_sources:
        st.markdown("---")
        st.subheader("📚 Nguồn Dữ Liệu Đang Hoạt Động (Active Sources)")
        src_table = []
        for s in active_sources:
            src_table.append({
                "Tên nguồn": s.get("source_name", "N/A"),
                "Mã băm SHA-256": s.get("file_hash", "")[:12] + "..." if s.get("file_hash") else "N/A",
                "Số bản ghi": s.get("record_count", 0),
                "Thời gian nạp": s.get("ingested_at", "N/A"),
                "Trạng thái": s.get("status", "ACTIVE"),
            })
        st.dataframe(src_table, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ==============================================================================
# TAB 3: 🛠️ CHẨN ĐOÁN & KIỂM ĐỊNH (DIAGNOSTICS & AUDIT)
# ==============================================================================
with tab_diagnostics:
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.markdown('<div class="panel-card-header">🛠️ Chẩn Đoán Hệ Thống & Kiểm Định Kỹ Thuật</div>', unsafe_allow_html=True)

    # 1. Thông số phần cứng & Cấu hình Runtime động
    st.markdown("#### 1. Thông số Phần cứng & Dịch vụ Runtime")
    hw_info = get_hardware_runtime_info()

    col_h1, col_h2, col_h3 = st.columns(3)
    with col_h1:
        st.markdown('<div class="metric-box">', unsafe_allow_html=True)
        st.markdown('<div class="metric-label">Thiết bị Embedding</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-value">{hw_info["device_name"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-caption">CUDA: {hw_info["cuda_version"]} | Thiết bị: {hw_info["device_type"]}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_h2:
        st.markdown('<div class="metric-box">', unsafe_allow_html=True)
        st.markdown('<div class="metric-label">Dịch vụ Ollama Local</div>', unsafe_allow_html=True)
        if ollama_info["online"]:
            st.markdown('<div class="metric-value" style="color:#16A34A;">🟢 Trực tuyến</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-caption">{settings.OLLAMA_BASE_URL}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="metric-value" style="color:#DC2626;">🔴 Ngoại tuyến</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-caption">{ollama_info.get("error") or "Không thể kết nối"}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_h2 if False else col_h3:
        st.markdown('<div class="metric-box">', unsafe_allow_html=True)
        st.markdown('<div class="metric-label">Thuật Toán RAG</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-value">Hybrid RRF (k={settings.RRF_K})</div>', unsafe_allow_html=True)
        st.markdown('<div class="metric-caption">BM25 Okapi + BGE-M3 (1024-d)</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 2. Phân biệt trạng thái Ollama Models
    st.markdown("#### 2. Trạng Thái Mô Hình LLM")
    col_m1, col_m2, col_m3 = st.columns(3)

    with col_m1:
        st.markdown("**Mô hình được cấu hình (Configured):**")
        st.code(settings.OLLAMA_MODEL, language="text")
        st.caption(f"Host: {settings.OLLAMA_BASE_URL} | Nhiệt độ T: {settings.LLM_TEMPERATURE}")

    with col_m2:
        st.markdown("**Mô hình đã cài đặt cục bộ (Installed):**")
        if ollama_info["online"] and ollama_info["installed_models"]:
            st.code("\n".join(ollama_info["installed_models"]), language="text")
        elif ollama_info["online"]:
            st.info("Chưa có model nào trong danh sách /api/tags.")
        else:
            st.caption("Chưa thể kiểm tra do dịch vụ Ollama đang ngoại tuyến.")

    with col_m3:
        st.markdown("**Mô hình đang nạp trong VRAM/RAM (Running):**")
        if ollama_info["online"] and ollama_info["running_models"]:
            st.code("\n".join(ollama_info["running_models"]), language="text")
        elif ollama_info["online"]:
            st.info("Đang ở trạng thái chờ (Chưa nạp model vào VRAM).")
        else:
            st.caption("Chưa thể kiểm tra do dịch vụ Ollama đang ngoại tuyến.")

    # 3. Ngưỡng Relevance Gate
    st.markdown("#### 3. Cấu hình Ngưỡng Lọc Phù Hợp (Relevance Gate)")
    col_g1, col_g2, col_g3 = st.columns(3)
    col_g1.metric("Direct Match Threshold", f"≥ {settings.DIRECT_MATCH_RRF_THRESHOLD}")
    col_g2.metric("RAG Generation Threshold", f"≥ {settings.RAG_RRF_THRESHOLD}")
    col_g3.metric("Fallback Threshold", f"≥ {settings.FALLBACK_RRF_THRESHOLD}")

    # 4. Công tắc Inspector kỹ thuật
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

    # 5. System Prompt thực tế (Read-only)
    st.markdown("---")
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

    # 6. Nhật ký truy vấn (Audit Trace Logs)
    st.markdown("---")
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

    st.markdown('</div>', unsafe_allow_html=True)


# --- FOOTER TỐI GIẢN CHUẨN TIẾNG VIỆT ---
st.markdown(
    """
    <div style="text-align: center; color: #94A3B8; font-size: 0.8rem; margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #F1F5F9;">
        Chatbox 2.0 • Trợ lý tra cứu từ vựng tiếng Anh theo ngữ cảnh • Streamlit Local RAG Architecture
    </div>
    """,
    unsafe_allow_html=True
)
