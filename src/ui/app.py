"""Giao diện Web Chatbox 2.0 phát triển trên Streamlit.

Giao diện hiện đại, tinh gọn, tập trung 100% vào trải nghiệm người dùng chatbox:
1. Bố cục 2 cột linh hoạt:
   - Cột bên trái: Bảng Cài Đặt & Quản Trị Kho Tri Thức (có nút đóng trực tiếp).
   - Cột bên phải: Khung Chatbox trung tâm rộng rãi, tối ưu trải nghiệm đọc và tra cứu.
2. Nút Bật/Tắt Cài Đặt 100% Native Python:
   - Người dùng bấm '✕ Đóng' hoặc '✕ Đóng Cài Đặt' thì bảng bên trái thu gọn, khung chat mở rộng toàn màn hình.
   - Người dùng bấm '⚙️ Mở Cài Đặt' ở thanh công cụ dưới (hoặc ở đầu trang) thì bảng bên trái lập tức mở lại ngay.
3. Không phụ thuộc vào JavaScript hay chevron ẩn của Streamlit, đảm bảo hoạt động tin cậy tuyệt đối.
"""

import html
import base64
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from src.llm.prompts import PROMPT_TEMPLATE
from src.ui.theme import CUSTOM_CSS

# Đường dẫn Avatar và dữ liệu base64 đồng bộ từ assets/
user_img_path = project_root / "assets" / "user.png"
bot_img_path = project_root / "assets" / "bot.png"

USER_AVATAR = str(user_img_path) if user_img_path.exists() else "👤"
BOT_AVATAR = str(bot_img_path) if bot_img_path.exists() else "🤖"

USER_B64 = base64.b64encode(user_img_path.read_bytes()).decode("ascii") if user_img_path.exists() else ""
BOT_B64 = base64.b64encode(bot_img_path.read_bytes()).decode("ascii") if bot_img_path.exists() else ""

# Cấu hình trang Streamlit
st.set_page_config(
    page_title="Trợ Lý Từ Vựng Tiếng Anh 🤖 - Local RAG Chatbox",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Áp dụng CSS Theme tinh gọn
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_resource(show_spinner="Đang khởi tạo các chỉ mục tri thức và mô hình...")
def get_chatbot_engine() -> ChatEngine:
    """Tạo singleton instance của ChatEngine và làm nóng các chỉ mục."""
    engine = ChatEngine()
    engine.warm_up()
    return engine


engine = get_chatbot_engine()
batch_manager = BatchIngestionManager()

# --- KHỞI TẠO SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "custom_system_prompt" not in st.session_state:
    st.session_state.custom_system_prompt = PROMPT_TEMPLATE
if "audit_logs" not in st.session_state:
    st.session_state.audit_logs = []
if "batch_report" not in st.session_state:
    st.session_state.batch_report = None
if "show_settings" not in st.session_state:
    st.session_state.show_settings = True  # Mặc định hiển thị bảng cài đặt bên trái


# ==============================================================================
# BỐ CỤC 2 CỘT LINH HOẠT: BẢNG CÀI ĐẶT (BÊN TRÁI) + KHUNG CHAT (BÊN PHẢI)
# ==============================================================================
if st.session_state.show_settings:
    col_settings, col_chat = st.columns([1, 2.3], gap="large")
else:
    col_settings = None
    col_chat = st.container()


# ------------------------------------------------------------------------------
# 1. BẢNG CÀI ĐẶT VÀ QUẢN TRỊ (BÊN TRÁI) - CÓ THỂ ĐÓNG VÀ MỞ LẠI DỄ DÀNG
# ------------------------------------------------------------------------------
if col_settings is not None:
    with col_settings:
        st.markdown('<div class="settings-panel-card">', unsafe_allow_html=True)

        # Header bảng cài đặt với nút Đóng trực tiếp
        col_sh1, col_sh2 = st.columns([2.5, 1.2])
        with col_sh1:
            st.markdown("### 🛠️ Cài Đặt")
        with col_sh2:
            if st.button("✕ Đóng", key="btn_close_settings_panel", use_container_width=True, help="Đóng bảng cài đặt bên trái"):
                st.session_state.show_settings = False
                st.rerun()

        st.caption("Quản trị kho tri thức và cấu hình hệ thống.")

        # 1. Quản Trị Kho Tri Thức (Batch Ingestion)
        with st.expander("📁 Quản Trị Kho Tri Thức", expanded=True):
            st.markdown("Nạp thêm tài liệu (PDF, Word, Excel, CSV, JSON, TXT, MD):")
            uploaded_batch_files = st.file_uploader(
                label="Chọn tệp tài liệu:",
                type=["pdf", "docx", "txt", "csv", "xlsx", "json", "jsonl", "md"],
                accept_multiple_files=True,
                key="panel_batch_uploader"
            )

            if uploaded_batch_files:
                ingestion_mode = st.radio(
                    "Chế độ nạp:",
                    options=["ADD", "REPLACE"],
                    index=0,
                    horizontal=True,
                    help="ADD: Thêm mới / Cập nhật trùng ID. REPLACE: Xóa toàn bộ DB cũ và nạp lại từ đầu.",
                    key="panel_ingest_mode"
                )

                if st.button("🚀 Nạp Tất Cả Tệp", key="panel_btn_process", type="primary", use_container_width=True):
                    settings.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
                    saved_paths: List[Path] = []
                    for uf in uploaded_batch_files:
                        target_path = settings.RAW_DATA_DIR / uf.name
                        with open(target_path, "wb") as f:
                            f.write(uf.getbuffer())
                        saved_paths.append(target_path)

                    with st.spinner("Đang xử lý nạp và lập chỉ mục dữ liệu..."):
                        report = batch_manager.ingest_batch(files=saved_paths, mode=ingestion_mode.lower())
                        new_records = batch_manager.loader.load_from_jsonl()
                        engine.update_knowledge_base(new_records)
                        st.session_state.batch_report = report
                        st.toast(f"Đã xử lý {report.total_files} tệp thành công!", icon="🎉")
                        st.rerun()

            # Danh mục nguồn dữ liệu đang hoạt động
            st.markdown("---")
            st.markdown("**📚 Danh Mục Nguồn Dữ Liệu:**")
            active_sources_list = batch_manager.get_active_sources()
            if not active_sources_list:
                st.caption("Chưa có tệp nạp ngoài. Dữ liệu chuẩn 3,725 cặp Q&A đang hoạt động.")
            else:
                for src in active_sources_list:
                    sid = src.get("source_id", "")
                    sname = src.get("file_name", "Không rõ")
                    scount = src.get("record_count", 0)
                    col_s1, col_s2 = st.columns([3, 1])
                    col_s1.caption(f"📄 {sname} ({scount} mục)")
                    if col_s2.button("Xóa", key=f"del_panel_{sid}"):
                        batch_manager.delete_source(sid)
                        new_recs = batch_manager.loader.load_from_jsonl()
                        engine.update_knowledge_base(new_recs)
                        st.toast(f"Đã xóa nguồn {sname}!", icon="🗑️")
                        st.rerun()

        # 2. Cấu Hình System Prompt
        with st.expander("⚙️ Cấu Hình System Prompt", expanded=False):
            current_prompt = st.text_area(
                label="Chỉ thị hệ thống (Prompt Template):",
                value=st.session_state.custom_system_prompt,
                height=180,
                key="panel_sys_prompt"
            )
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                if st.button("Lưu Prompt", key="btn_save_prompt_panel", type="primary", use_container_width=True):
                    st.session_state.custom_system_prompt = current_prompt
                    st.toast("Đã lưu Prompt mới!", icon="✅")
            with col_p2:
                if st.button("Mặc Định", key="btn_reset_prompt_panel", use_container_width=True):
                    st.session_state.custom_system_prompt = PROMPT_TEMPLATE
                    st.toast("Đã khôi phục Prompt mặc định!", icon="🔄")
                    st.rerun()

        # 3. Nhật Ký Truy Vấn (Audit Log)
        with st.expander("📋 Nhật Ký Truy Vấn", expanded=False):
            st.markdown(f"**Tổng số lượt:** `{len(st.session_state.audit_logs)}`")
            if st.session_state.audit_logs:
                if st.button("Xóa Nhật Ký", key="btn_clear_log_panel", use_container_width=True):
                    st.session_state.audit_logs = []
                    st.toast("Đã xóa nhật ký!", icon="🧹")
                    st.rerun()
                st.download_button(
                    label="📥 Tải Nhật Ký (JSON)",
                    data=json.dumps(st.session_state.audit_logs, ensure_ascii=False, indent=2),
                    file_name="chatbox_audit_logs.json",
                    mime="application/json",
                    use_container_width=True,
                    key="btn_download_log_panel"
                )
            else:
                st.caption("Chưa có nhật ký truy vấn.")

        # 4. Trạng Thái Hệ Thống
        with st.expander("ℹ️ Trạng Thái Hệ Thống", expanded=False):
            is_ollama_ready = engine.llm_client.is_service_ready()
            if is_ollama_ready:
                st.success("🟢 Ollama Local: Sẵn sàng")
            else:
                st.error("🔴 Ollama Local: Chưa kết nối")

            active_w = engine.tracker.active_word
            if active_w:
                st.info(f"🎯 Từ vựng active: **{active_w}**")
            else:
                st.caption("🎯 Chưa có từ vựng active")

            st.markdown(f"📚 **Kho tri thức:** `{len(engine.records):,} Q&A`")
            st.markdown(f"🤖 **Mô hình:** `{settings.OLLAMA_MODEL}`")
            st.markdown("🧠 **Embeddings:** `BGE-M3` (1024-d)")
            st.markdown("🔎 **NLU Intent:** `PhoBERT-base-v2`")

        st.markdown('</div>', unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# 2. KHU VỰC CHATBOX CHÍNH (BÊN PHẢI HOẶC TOÀN MÀN HÌNH NẾU ĐÓNG CÀI ĐẶT)
# ------------------------------------------------------------------------------
with col_chat:
    # Header chính
    is_ollama_on = engine.llm_client.is_service_ready()
    ollama_badge = '<span class="chatbox-badge-item active">🟢 Local AI Ready</span>' if is_ollama_on else '<span class="chatbox-badge-item">🔴 Ollama Offline</span>'

    st.markdown(
        f"""
        <div class="chatbox-header-wrap">
            <div class="chatbox-header-title">Trợ Lý Từ Vựng Tiếng Anh 🤖</div>
            <div class="chatbox-header-subtitle">
                Tra cứu định nghĩa, phát âm, từ loại, ví dụ và ngữ cảnh bằng tiếng Việt tự nhiên
            </div>
            <div class="chatbox-badges">
                {ollama_badge}
                <span class="chatbox-badge-item">📚 {len(engine.records):,} Từ vựng</span>
                <span class="chatbox-badge-item">⚡ Qwen2.5:7B + PhoBERT + BGE-M3</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Nếu bảng cài đặt đang đóng, hiển thị nút mở nhanh ở đầu trang
    if not st.session_state.show_settings:
        col_open1, col_open2, col_open3 = st.columns([1, 2, 1])
        with col_open2:
            if st.button("⚙️ Mở Bảng Cài Đặt & Quản Trị Kho Tri Thức", key="btn_open_settings_top", use_container_width=True):
                st.session_state.show_settings = True
                st.rerun()

    # Khung cuộn tin nhắn hội thoại
    chat_msg_container = st.container(height=520, border=True)

    with chat_msg_container:
        # Lời chào mặc định khi chưa có tin nhắn
        if not st.session_state.messages:
            st.markdown(
                f"""
                <div class="bot-msg-wrapper">
                    <img src="data:image/png;base64,{BOT_B64}" class="bot-avatar-img" />
                    <div class="bot-bubble-box">
                        <strong>Xin chào 👋!</strong> Tôi là trợ lý tra cứu từ vựng tiếng Anh chạy hoàn toàn cục bộ trên máy tính của bạn.<br><br>
                        Bạn có thể hỏi bất kỳ từ vựng nào (định nghĩa, ví dụ câu, từ loại, từ đồng nghĩa hoặc câu hỏi ôn tập) bằng tiếng Việt tự nhiên!
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        # Hiển thị lịch sử hội thoại
        for msg in st.session_state.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "user":
                # Tin nhắn người dùng nằm ở BÊN PHẢI
                escaped_c = html.escape(content).replace("\n", "<br>")
                st.markdown(
                    f"""
                    <div class="user-msg-wrapper">
                        <div class="user-bubble-box">{escaped_c}</div>
                        <img src="data:image/png;base64,{USER_B64}" class="user-avatar-img" />
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                # Tin nhắn Chatbot nằm ở BÊN TRÁI
                st.markdown('<div class="bot-msg-wrapper">', unsafe_allow_html=True)
                with st.chat_message("assistant", avatar=BOT_AVATAR):
                    st.markdown(content)
                st.markdown('</div>', unsafe_allow_html=True)

    # Ô nhập liệu tin nhắn chính
    with st.form(key="chat_message_form", clear_on_submit=True):
        col_input, col_btn = st.columns([8.8, 1.2])
        with col_input:
            user_input_text = st.text_input(
                "Tin nhắn",
                placeholder="Nhập câu hỏi hoặc từ vựng cần tra cứu... (Ví dụ: 'abandon là gì?', 'ví dụ từ resilient')",
                label_visibility="collapsed",
                key="chat_main_input"
            )
        with col_btn:
            send_submitted = st.form_submit_button("Gửi ➤", use_container_width=True, type="primary")

    # Xác định câu hỏi cần xử lý từ input
    active_query = user_input_text.strip() if (send_submitted and user_input_text and user_input_text.strip()) else None

    # Thực thi truy vấn nếu có
    if active_query:
        # 1. Thêm tin nhắn của User vào danh sách
        st.session_state.messages.append({"role": "user", "content": active_query})

        with chat_msg_container:
            escaped_q = html.escape(active_query).replace("\n", "<br>")
            st.markdown(
                f"""
                <div class="user-msg-wrapper">
                    <div class="user-bubble-box">{escaped_q}</div>
                    <img src="data:image/png;base64,{USER_B64}" class="user-avatar-img" />
                </div>
                """,
                unsafe_allow_html=True
            )

            # 2. Xử lý câu trả lời từ ChatEngine
            st.markdown('<div class="bot-msg-wrapper">', unsafe_allow_html=True)
            with st.chat_message("assistant", avatar=BOT_AVATAR):
                with st.spinner("Đang tra cứu từ điển và tổng hợp câu trả lời..."):
                    response: ChatResponse = engine.ask(active_query)

                # Hiệu ứng stream chữ
                placeholder = st.empty()
                streamed = ""
                for char in response.answer:
                    streamed += char
                    placeholder.markdown(streamed + "▌")
                    time.sleep(0.003)
                placeholder.markdown(response.answer)
            st.markdown('</div>', unsafe_allow_html=True)

        # 3. Ghi vào session state
        st.session_state.messages.append({
            "role": "assistant",
            "content": response.answer,
            "meta": response
        })

        # 4. Ghi log sự kiện cho phần Cài Đặt
        st.session_state.audit_logs.append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "query": active_query,
            "mode": response.mode,
            "intent": response.intent,
            "active_word": engine.tracker.active_word,
            "record_id": response.record_id,
            "rrf_score": response.rrf_score,
            "latency_ms": response.latency_ms,
            "answer": response.answer
        })
        st.rerun()

    # Hàng nút tác vụ tiện ích (Action Bar)
    st.markdown('<div class="chat-action-bar">', unsafe_allow_html=True)
    col_b1, col_b2, col_b3, col_b4 = st.columns(4)

    with col_b1:
        if st.button("🧹 Xóa Đoạn Chat", key="btn_clear_chat", use_container_width=True, help="Xóa các tin nhắn trên màn hình"):
            st.session_state.messages = []
            st.toast("Đã xóa đoạn chat trên màn hình.", icon="🧹")
            st.rerun()

    with col_b2:
        if st.button("🔄 Cuộc Trò Chuyện Mới", key="btn_reset_chat", use_container_width=True, help="Xóa tin nhắn và đặt lại chủ đề từ vựng"):
            st.session_state.messages = []
            engine.tracker.clear()
            st.toast("Đã khởi tạo phiên trò chuyện mới.", icon="🔄")
            st.rerun()

    with col_b3:
        if st.button("↩️ Hoàn Tác Lượt Trước", key="btn_undo_chat", use_container_width=True, help="Hoàn tác lượt hỏi đáp gần nhất"):
            if st.session_state.messages:
                while st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
                    st.session_state.messages.pop()
                if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
                    st.session_state.messages.pop()
                if engine.tracker.history:
                    engine.tracker.history.pop()
                    engine.tracker.active_word = engine.tracker.history[-1].active_word if engine.tracker.history else None
                st.toast("Đã hoàn tác lượt hội thoại gần nhất.", icon="↩️")
                st.rerun()

    with col_b4:
        toggle_label = "✕ Đóng Cài Đặt" if st.session_state.show_settings else "⚙️ Mở Cài Đặt"
        if st.button(toggle_label, key="btn_toggle_settings_bottom", use_container_width=True, help="Bật / tắt bảng cài đặt bên trái"):
            st.session_state.show_settings = not st.session_state.show_settings
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
