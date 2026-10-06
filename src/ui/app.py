"""Giao diện Web Chatbox 2.0 phát triển trên Streamlit.

Đồng bộ toàn diện phong cách giao diện và bố cục từ rag-chatbot-main:
1. Header & Typography: 'Local RAG Chatbot 🤖' phong cách Soft Slate.
2. Cấu trúc 4 Tabs chính:
   - 💬 Interface: Giao diện Tra Cứu Từ Vựng (Bố cục 2 cột: Setting Panel bên trái + Chatbot bên phải).
   - ⚙️ Setting: Cấu hình System Prompt và các siêu tham số RAG.
   - 📋 Output: Nhật ký sự kiện, kiểm định truy vấn & Provenance Audit Trace.
   - 📁 Quản Trị Kho Tri Thức: Batch Multi-File Ingestion & Quản lý nguồn.
3. Chat Controls & Avatars:
   - Avatar icon đồng bộ từ assets/user.png và assets/bot.png.
   - Trạng thái Status: Ready!, Answering!, Completed!
   - Bộ chọn Chat Mode: QA (Tra cứu chuẩn xác) vs Chat (Hội thoại ngữ nghĩa).
   - Bộ 4 nút tác vụ chuẩn demo.png: Hide/Show Setting, Undo, Clear, Reset.
"""

import html
import base64
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

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
    page_title="Local RAG Chatbot 🤖 - English Vocabulary Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Áp dụng CSS Theme đồng bộ từ rag-chatbot-main
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
if "show_setting" not in st.session_state:
    st.session_state.show_setting = True
if "status" not in st.session_state:
    st.session_state.status = "Ready!"
if "chat_mode" not in st.session_state:
    st.session_state.chat_mode = "QA"
if "language" not in st.session_state:
    st.session_state.language = "vi"
if "model_name" not in st.session_state:
    st.session_state.model_name = settings.OLLAMA_MODEL
if "dev_mode" not in st.session_state:
    st.session_state.dev_mode = True
if "custom_system_prompt" not in st.session_state:
    st.session_state.custom_system_prompt = PROMPT_TEMPLATE
if "audit_logs" not in st.session_state:
    st.session_state.audit_logs = []
if "batch_report" not in st.session_state:
    st.session_state.batch_report = None
if "failed_files_to_retry" not in st.session_state:
    st.session_state.failed_files_to_retry = {}


# --- HEADER GIAO DIỆN (CHÍNH XÁC PHONG CÁCH demo.png) ---
st.markdown('<div class="gr-app-title">Local RAG Chatbot 🤖</div>', unsafe_allow_html=True)

# --- 4 TABS ĐIỀU HƯỚNG CHÍNH ---
tab_interface, tab_setting, tab_output, tab_knowledge = st.tabs([
    "Interface",
    "Setting",
    "Output",
    "📁 Quản Trị Kho Tri Thức"
])


# ==============================================================================
# TAB 1: GIAO DIỆN CHÍNH (INTERFACE TAB) — BỐ CỤC 2 CỘT CHUẨN demo.png
# ==============================================================================
with tab_interface:
    # Điều phối hiển thị 2 cột nếu show_setting = True, hoặc 1 cột nếu ẩn
    if st.session_state.show_setting:
        col_setting, col_chat = st.columns([1, 2.5], gap="medium")
    else:
        col_setting = None
        col_chat = st.container()

    # --- CỘT TRÁI: SETTING PANEL ---
    if col_setting is not None:
        with col_setting:
            st.markdown('<div class="panel-card">', unsafe_allow_html=True)

            # 1. Trạng thái Status (Chuẩn Gradio Textbox demo.png)
            curr_status = st.session_state.status
            st.markdown(
                f"""
                <div class="gr-label">Status</div>
                <div class="gr-status-textbox">{curr_status}</div>
                """,
                unsafe_allow_html=True
            )

            # 2. Lựa chọn Ngôn ngữ (Language radio dạng pill)
            st.markdown("<div class='gr-label'>Language</div>", unsafe_allow_html=True)
            lang_idx = 0 if st.session_state.language == "vi" else 1
            selected_lang = st.radio(
                "Language",
                options=["vi", "eng"],
                index=lang_idx,
                horizontal=True,
                label_visibility="collapsed",
                key="radio_lang_setting"
            )
            st.session_state.language = selected_lang

            # 3. Hiển thị Trình tự Pipeline cố định (Architecture Lock - Không chia rẽ model)
            st.markdown("<div class='gr-label' style='margin-top: 10px;'>Pipeline Trình Tự Bắt Buộc:</div>", unsafe_allow_html=True)
            pipeline_options = [
                "PhoBERT ➔ BM25 + BGE-M3 ➔ RRF Gate ➔ Qwen2.5:7B"
            ]
            st.selectbox(
                "Pipeline Trình Tự Bắt Buộc:",
                options=pipeline_options,
                index=0,
                disabled=True,
                label_visibility="collapsed",
                key="select_model_setting",
                help="Pipeline thống nhất: 1. PhoBERT (Ý định) ➔ 2. BM25 + BGE-M3 (Truy xuất) ➔ 3. RRF Gate (Lọc) ➔ 4. Qwen2.5:7B (Sinh câu trả lời)."
            )

            # 4. Thêm tài liệu nhanh (Add Documents)
            st.markdown("<div class='gr-label' style='margin-top: 14px;'>📄 Add Documents</div>", unsafe_allow_html=True)
            uploaded_doc_files = st.file_uploader(
                "Add Documents",
                type=["txt", "pdf", "csv", "xlsx", "docx", "json", "jsonl", "md"],
                accept_multiple_files=True,
                label_visibility="collapsed",
                key="inline_doc_uploader"
            )

            col_doc1, col_doc2 = st.columns(2)
            with col_doc1:
                st.markdown('<div class="btn-upload">', unsafe_allow_html=True)
                if st.button("Upload", key="btn_doc_upload", use_container_width=True, type="primary"):
                    if uploaded_doc_files:
                        settings.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
                        temp_paths: List[Path] = []
                        for uf in uploaded_doc_files:
                            t_path = settings.RAW_DATA_DIR / uf.name
                            with open(t_path, "wb") as f:
                                f.write(uf.getbuffer())
                            temp_paths.append(t_path)

                        with st.spinner("Đang nạp và lập chỉ mục tài liệu vào kho tri thức..."):
                            rep = batch_manager.ingest_batch(temp_paths)
                            new_recs = batch_manager.loader.load_from_jsonl()
                            engine.update_knowledge_base(new_recs)
                            st.session_state.status = "Processing documents 📄 completed!"
                            st.session_state.batch_report = rep
                            st.toast(f"Đã nạp {rep.success_count} tệp thành công!", icon="✅")
                            st.rerun()
                    else:
                        st.warning("Vui lòng chọn ít nhất 1 tệp!")
                st.markdown('</div>', unsafe_allow_html=True)

            with col_doc2:
                st.markdown('<div class="btn-reset">', unsafe_allow_html=True)
                if st.button("Reset", key="btn_doc_reset", use_container_width=True):
                    st.session_state.status = "Ready!"
                    st.toast("Đã đặt lại danh sách tệp đính kèm.", icon="🔄")
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            st.markdown("---")

            # 5. Giám sát hệ thống & Chủ đề hiện hành
            is_ollama_ready = engine.llm_client.is_service_ready()
            if is_ollama_ready:
                st.markdown("🟢 **Ollama Local:** Sẵn sàng")
            else:
                st.markdown("🔴 **Ollama Local:** Chưa bật service")

            active_w = engine.tracker.active_word
            if active_w:
                st.markdown(f"🎯 **Từ vựng active:** `{active_w}`")
            else:
                st.caption("🎯 Chưa có từ vựng active")

            st.caption(f"📚 **Kho tri thức:** `{len(engine.records):,}` cặp Q&A")

            # Checkbox hiện Inspector
            st.session_state.dev_mode = st.checkbox(
                "Hiện Inspector kỹ thuật",
                value=st.session_state.dev_mode,
                help="Hiển thị PhoBERT Intent, RRF score, BM25 rank, BGE-M3 rank và Record ID.",
                key="checkbox_dev_mode"
            )

            st.markdown('</div>', unsafe_allow_html=True)

    # --- CỘT PHẢI: KHUNG CHATBOT CHÍNH (MAIN CHAT AREA) ---
    with col_chat:
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.markdown('<div class="panel-card-header">💬 Chatbot</div>', unsafe_allow_html=True)

        # Khung tin nhắn cuộn tròn chuẩn demo.png
        chat_msg_container = st.container(height=480)
        with chat_msg_container:
            # Lời chào mặc định nếu chưa có tin nhắn
            if not st.session_state.messages:
                st.markdown(
                    f"""
                    <div class="bot-msg-wrapper">
                        <img src="data:image/png;base64,{BOT_B64}" class="bot-avatar-img" />
                        <div class="bot-bubble-box">
                            Hi 👋, how can I help you today? Tôi là trợ lý tra cứu từ vựng tiếng Anh. Bạn có thể tra nghĩa, ví dụ, từ đồng nghĩa hoặc câu hỏi từ vựng tiếng Anh bằng tiếng Việt tự nhiên!
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            # Hiển thị lịch sử hội thoại
            for msg in st.session_state.messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                meta: Optional[ChatResponse] = msg.get("meta")

                if role == "user":
                    # Tin nhắn người dùng nằm ở BÊN PHẢI (User on the RIGHT)
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
                    # Tin nhắn Chatbot nằm ở BÊN TRÁI (Chatbot on the LEFT)
                    st.markdown('<div class="bot-msg-wrapper">', unsafe_allow_html=True)
                    with st.chat_message("assistant", avatar=BOT_AVATAR):
                        st.markdown(content)

                        # Hiển thị Provenance Inspector nếu bật dev_mode
                        if st.session_state.dev_mode and meta is not None:
                            with st.expander(f"🔍 Inspector: {meta.mode} | Intent: {meta.intent or 'N/A'} (RRF: {meta.rrf_score:.4f})"):
                                c1, c2, c3, c4 = st.columns(4)
                                c1.metric("Response Mode", meta.mode)
                                c2.metric("PhoBERT Intent", meta.intent or "N/A")
                                c3.metric("RRF Score", f"{meta.rrf_score:.4f}")
                                c4.metric("Độ trễ", f"{meta.latency_ms:.1f} ms")

                                if meta.record_id:
                                    st.markdown(f"**Mã bản ghi:** `{meta.record_id}` | **Từ vựng:** `{meta.word}` | **Nguồn:** `{meta.source}`")

                                if meta.candidates:
                                    st.markdown("**Top ứng viên trích xuất sau khi hợp nhất RRF (k=60):**")
                                    c_table = []
                                    for rk, cand in enumerate(meta.candidates, 1):
                                        c_table.append({
                                            "Hạng RRF": f"#{rk}",
                                            "Mã Record": cand.record.record_id,
                                            "Từ vựng": cand.record.word or "N/A",
                                            "Nguồn": cand.record.source or cand.record.sheet,
                                            "Điểm BM25": f"{cand.bm25_score:.2f} (#{cand.bm25_rank})",
                                            "Điểm BGE-M3": f"{cand.bge_score:.4f} (#{cand.bge_rank})",
                                            "Điểm RRF": f"{cand.rrf_score:.4f}"
                                        })
                                    st.dataframe(c_table, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)

        # Hàng nhập tin nhắn inline trong card chuẩn demo.png
        with st.form(key="chat_inline_form", clear_on_submit=True):
            col_m1, col_m2, col_m3 = st.columns([1.5, 7.5, 1])
            with col_m1:
                chat_mode_val = st.selectbox(
                    "Chế độ",
                    options=["QA", "chat"],
                    index=0 if st.session_state.chat_mode == "QA" else 1,
                    label_visibility="collapsed",
                    help="QA: Tra cứu chuẩn xác | chat: Đàm thoại giải thích ngữ nghĩa",
                    key="select_chat_mode"
                )
                st.session_state.chat_mode = chat_mode_val

            with col_m2:
                prompt_input = st.text_input(
                    "Tin nhắn",
                    placeholder="Enter you message:",
                    label_visibility="collapsed",
                    key="chat_inline_text"
                )

            with col_m3:
                submitted = st.form_submit_button("➤", use_container_width=True)

        # Xử lý khi người dùng gửi câu hỏi
        if submitted and prompt_input:
            st.session_state.status = "Answering!"
            # 1. Ghi nhận tin nhắn người dùng
            st.session_state.messages.append({"role": "user", "content": prompt_input})
            with chat_msg_container:
                escaped_input = html.escape(prompt_input).replace("\n", "<br>")
                st.markdown(
                    f"""
                    <div class="user-msg-wrapper">
                        <div class="user-bubble-box">{escaped_input}</div>
                        <img src="data:image/png;base64,{USER_B64}" class="user-avatar-img" />
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # 2. Gọi ChatEngine xử lý RAG
                st.markdown('<div class="bot-msg-wrapper">', unsafe_allow_html=True)
                with st.chat_message("assistant", avatar=BOT_AVATAR):
                    with st.spinner("Đang tra cứu từ điển và tổng hợp tri thức..."):
                        response: ChatResponse = engine.ask(prompt_input)

                    # Hiệu ứng typing stream
                    msg_placeholder = st.empty()
                    streamed_text = ""
                    for char in response.answer:
                        streamed_text += char
                        msg_placeholder.markdown(streamed_text + "▌")
                        time.sleep(0.003)
                    msg_placeholder.markdown(response.answer)

                    # Hiển thị Inspector ngay sau khi trả lời nếu bật
                    if st.session_state.dev_mode:
                        with st.expander(f"🔍 Inspector: {response.mode} | Intent: {response.intent or 'N/A'} (RRF: {response.rrf_score:.4f})"):
                            c1, c2, c3, c4 = st.columns(4)
                            c1.metric("Response Mode", response.mode)
                            c2.metric("PhoBERT Intent", response.intent or "N/A")
                            c3.metric("RRF Score", f"{response.rrf_score:.4f}")
                            c4.metric("Độ trễ", f"{response.latency_ms:.1f} ms")
                st.markdown('</div>', unsafe_allow_html=True)

            # 3. Lưu vào session state
            st.session_state.messages.append({
                "role": "assistant",
                "content": response.answer,
                "meta": response
            })
            st.session_state.status = "Completed!"

            # 4. Ghi log sự kiện vào Output Tab
            st.session_state.audit_logs.append({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "query": prompt_input,
                "mode": response.mode,
                "intent": response.intent,
                "active_word": engine.tracker.active_word,
                "record_id": response.record_id,
                "rrf_score": response.rrf_score,
                "latency_ms": response.latency_ms,
                "answer": response.answer
            })
            st.rerun()

        # Hàng 4 nút tác vụ chuẩn demo.png (Hide/Show Setting, Undo, Clear, Reset)
        st.markdown('<div class="chat-action-bar">', unsafe_allow_html=True)
        btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)

        with btn_col1:
            toggle_label = "Hide Setting" if st.session_state.show_setting else "Show Setting"
            if st.button(toggle_label, key="btn_toggle_setting", use_container_width=True):
                st.session_state.show_setting = not st.session_state.show_setting
                st.rerun()

        with btn_col2:
            if st.button("Undo", key="btn_chat_undo", use_container_width=True):
                if st.session_state.messages:
                    while st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
                        st.session_state.messages.pop()
                    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
                        st.session_state.messages.pop()
                    if engine.tracker.history:
                        engine.tracker.history.pop()
                        engine.tracker.active_word = engine.tracker.history[-1].active_word if engine.tracker.history else None
                    st.session_state.status = "Ready!"
                    st.toast("Đã hoàn tác lượt hội thoại gần nhất.", icon="↩️")
                    st.rerun()

        with btn_col3:
            if st.button("Clear", key="btn_chat_clear", use_container_width=True):
                st.session_state.messages = []
                st.session_state.status = "Ready!"
                st.toast("Đã xóa tin nhắn màn hình chat.", icon="🧹")
                st.rerun()

        with btn_col4:
            if st.button("Reset", key="btn_chat_reset", use_container_width=True):
                st.session_state.messages = []
                engine.tracker.clear()
                st.session_state.status = "Ready!"
                st.toast("Đã đặt lại toàn bộ phiên hội thoại.", icon="🔄")
                st.rerun()

        st.markdown('</div></div>', unsafe_allow_html=True)


# ==============================================================================
# TAB 2: CẤU HÌNH HỆ THỐNG (SETTING TAB) — CHUẨN rag-chatbot-main
# ==============================================================================
with tab_setting:
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.markdown('<div class="panel-card-header">⚙️ System Prompt & Hyperparameters</div>', unsafe_allow_html=True)

    st.markdown("#### System Prompt")
    st.caption("Cấu hình chỉ thị kiểm soát hành vi tổng hợp tri thức của Qwen2.5:7B:")
    
    current_prompt = st.text_area(
        label="System Prompt Content",
        value=st.session_state.custom_system_prompt,
        height=240,
        label_visibility="collapsed",
        key="textarea_system_prompt"
    )

    col_p1, col_p2 = st.columns([1, 1])
    with col_p1:
        if st.button("Set System Prompt", key="btn_set_sys_prompt", type="primary", use_container_width=True):
            st.session_state.custom_system_prompt = current_prompt
            st.success("Đã cập nhật System Prompt thành công!")
            st.toast("System prompt updated!", icon="✅")

    with col_p2:
        if st.button("Reset to Default Prompt", key="btn_reset_sys_prompt", use_container_width=True):
            st.session_state.custom_system_prompt = PROMPT_TEMPLATE
            st.info("Đã khôi phục System Prompt gốc của dự án.")
            st.rerun()

    st.markdown("---")
    st.markdown("#### Siêu Tham Số Truy Xuất & Sinh Ngữ Nghĩa")

    col_h1, col_h2, col_h3 = st.columns(3)
    with col_h1:
        st.slider("Temperature LLM (Độ sáng tạo)", min_value=0.0, max_value=1.0, value=settings.LLM_TEMPERATURE, step=0.05, disabled=True, key="slider_llm_temp")
        st.caption("Khóa ở mức 0.1 để đảm bảo chống suy diễn tự do (Zero Hallucination).")

    with col_h2:
        st.number_input("RRF Smoothing Parameter (k)", min_value=10, max_value=100, value=settings.RRF_K, disabled=True, key="input_rrf_k")
        st.caption("Hệ số điều hòa chuẩn k=60 của Reciprocal Rank Fusion.")

    with col_h3:
        st.number_input("Top-K Retrieval Candidates", min_value=1, max_value=10, value=settings.TOP_K_RETRIEVAL, disabled=True, key="input_top_k")
        st.caption("Số lượng đoạn trích xuất có điểm RRF cao nhất gửi tới LLM.")

    st.markdown('</div>', unsafe_allow_html=True)


# ==============================================================================
# TAB 3: NHẬT KÝ & KIỂM ĐỊNH (OUTPUT TAB) — CHUẨN rag-chatbot-main
# ==============================================================================
with tab_output:
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.markdown('<div class="panel-card-header">📋 System Logs & Audit Trace</div>', unsafe_allow_html=True)

    col_out1, col_out2 = st.columns([4, 1])
    with col_out1:
        st.markdown(f"**Tổng số lượt truy vấn đã ghi nhận:** `{len(st.session_state.audit_logs)}` lượt")
    with col_out2:
        if st.button("Clear Log", key="btn_clear_audit_log", use_container_width=True):
            st.session_state.audit_logs = []
            st.toast("Đã xóa toàn bộ nhật ký truy vấn.", icon="🧹")
            st.rerun()

    if not st.session_state.audit_logs:
        st.info("Chưa có nhật ký truy vấn nào trong phiên hiện tại. Hãy đặt câu hỏi ở tab Interface để theo dõi log.")
    else:
        log_markdown_lines = []
        log_markdown_lines.append("# CHATBOX 2.0 AUDIT LOG TRACE")
        log_markdown_lines.append(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

        for idx, entry in enumerate(reversed(st.session_state.audit_logs), 1):
            log_markdown_lines.append(
                f"### [Query #{idx}] {entry['timestamp']}\n"
                f"- **User Query:** `{entry['query']}`\n"
                f"- **Response Mode:** `{entry['mode']}`\n"
                f"- **PhoBERT Intent:** `{entry['intent']}`\n"
                f"- **Active Word:** `{entry['active_word']}`\n"
                f"- **Primary Record ID:** `{entry['record_id']}`\n"
                f"- **RRF Score:** `{entry['rrf_score']:.4f}`\n"
                f"- **Latency:** `{entry['latency_ms']:.1f} ms`\n"
                f"- **Answer Snippet:** {entry['answer'][:150]}...\n"
                f"{'-'*40}"
            )

        full_log_text = "\n".join(log_markdown_lines)
        st.code(full_log_text, language="markdown")

        st.download_button(
            label="📥 Tải Nhật Ký Audit (JSON)",
            data=json.dumps(st.session_state.audit_logs, ensure_ascii=False, indent=2),
            file_name="chatbox2_audit_log.json",
            mime="application/json",
            use_container_width=True,
            key="btn_download_audit_json"
        )

    st.markdown('</div>', unsafe_allow_html=True)


# ==============================================================================
# TAB 4: QUẢN TRỊ KHO TRI THỨC (BATCH MULTI-FILE INGESTION TAB)
# ==============================================================================
with tab_knowledge:
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.markdown('<div class="panel-card-header">📁 Quản Trị Kho Tri Thức (Batch Ingestion)</div>', unsafe_allow_html=True)

    st.markdown(
        "Hỗ trợ Admin tải lên đồng thời nhiều tệp thuộc **8 định dạng tài liệu** khác nhau "
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
                "Trạng thái": "Sẵn sàng xử lý (QUEUED)"
            })
        st.dataframe(file_preview_data, use_container_width=True)

        # Nút bấm bắt đầu xử lý toàn bộ batch
        if st.button("🚀 Bắt Đầu Xử Lý Tất Cả Tệp (Process All Files)", key="btn_process_batch_all", type="primary", use_container_width=True):
            settings.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
            saved_paths: List[Path] = []

            for uf in uploaded_batch_files:
                target_path = settings.RAW_DATA_DIR / uf.name
                with open(target_path, "wb") as f:
                    f.write(uf.getbuffer())
                saved_paths.append(target_path)

            progress_bar = st.progress(0, text="Đang chuẩn bị nạp batch...")

            def ui_batch_callback(msg: str, pct: float, current_res: Optional[Any]):
                progress_bar.progress(int(pct * 100), text=msg)

            # Thực thi Batch Ingestion
            report = batch_manager.ingest_batch(
                files=saved_paths,
                progress_callback=ui_batch_callback
            )

            # Cập nhật nóng ChatEngine trong bộ nhớ
            new_records = batch_manager.loader.load_from_jsonl()
            engine.update_knowledge_base(new_records)

            st.session_state.batch_report = report
            progress_bar.progress(100, text="Hoàn tất xử lý batch!")
            st.toast("Hoàn tất xử lý Batch Multi-File Ingestion!", icon="🎉")
            st.rerun()

    # 2. Hiển thị Báo Cáo Tổng Hợp Batch Ingestion
    report = st.session_state.batch_report
    if report:
        st.markdown("---")
        st.subheader("📊 Báo Cáo Xử Lý Batch (Batch Ingestion Report)")

        # Thống kê tổng quan
        col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
        col_s1.metric("Tổng số tệp", report.total_files)
        col_s2.metric("Thành công (SUCCESS)", report.success_count)
        col_s3.metric("Bỏ qua (SKIPPED)", report.skipped_count)
        col_s4.metric("Thất bại (FAILED)", report.failed_count)
        col_s5.metric("Bản ghi nạp mới", f"+{report.total_records_added:,}")

        # Trạng thái tổng thể
        if report.batch_status == BatchStatus.SUCCESS:
            st.success(f"🎉 **Trạng thái Batch:** `{report.batch_status.value}` — Toàn bộ tệp đã được xử lý và lập chỉ mục hoàn tất!")
        elif report.batch_status == BatchStatus.PARTIAL_SUCCESS:
            st.warning(f"⚠️ **Trạng thái Batch:** `{report.batch_status.value}` — Đã nạp thành công các tệp hợp lệ. Một số tệp bị bỏ qua hoặc lỗi.")
        else:
            st.error(f"❌ **Trạng thái Batch:** `{report.batch_status.value}` — Không tệp nào được đưa vào cơ sở tri thức.")

        # Chi tiết trạng thái từng tệp (File Status Table)
        file_status_rows = []
        failed_files = {}

        for fr in report.file_results:
            st_text = fr.status.value if isinstance(fr.status, FileStatus) else fr.status
            file_status_rows.append({
                "Tên tệp": fr.file_name,
                "Định dạng": fr.file_type.upper(),
                "Trạng thái": st_text,
                "Trích xuất": fr.records_extracted,
                "Thêm mới": fr.records_added,
                "Trùng lặp": fr.duplicates_skipped,
                "Thời gian (s)": fr.elapsed_seconds,
                "Lý do / Ghi chú": fr.reason or "Thành công"
            })
            if fr.status == FileStatus.FAILED:
                failed_files[fr.file_name] = fr

        st.dataframe(file_status_rows, use_container_width=True)

        # Hỗ trợ Retry độc lập cho tệp lỗi
        if failed_files:
            st.subheader("🔄 Thử Lại Tệp Thất Bại (Retry Failed Files)")
            for f_name, f_obj in failed_files.items():
                col_r1, col_r2 = st.columns([3, 1])
                col_r1.error(f"**{f_name}**: {f_obj.reason}")
                if col_r2.button(f"Retry {f_name}", key=f"retry_{f_name}"):
                    retry_path = Path(f_obj.file_path)
                    if retry_path.exists():
                        retry_report = batch_manager.ingest_batch([retry_path])
                        new_records = batch_manager.loader.load_from_jsonl()
                        engine.update_knowledge_base(new_records)
                        st.toast(f"Đã thử lại {f_name}: {retry_report.batch_status.value}")
                        st.session_state.batch_report = retry_report
                        st.rerun()

    # 3. Quản Lý Nguồn Dữ Liệu Hiện Có (Source Management)
    st.markdown("---")
    st.subheader("📚 Danh Mục Nguồn Dữ Liệu Đang Hoạt Động (Active Sources)")
    st.caption("Quản lý danh sách các tệp nguồn đã được đưa vào Knowledge Base. Hỗ trợ xóa nguồn hoặc tái lập chỉ mục.")

    active_sources_list = batch_manager.get_active_sources()
    if not active_sources_list:
        st.info("Chưa có nguồn tệp nào được đăng ký trong manifest. Dữ liệu mặc định 3,725 cặp Q&A vẫn sẵn sàng.")
    else:
        for src in active_sources_list:
            sid = src.get("source_id", "")
            sname = src.get("file_name", "Không rõ")
            stype = src.get("file_type", "").upper()
            scount = src.get("record_count", 0)
            sdate = src.get("ingested_at", "N/A")

            col_src1, col_src2, col_src3 = st.columns([3, 1, 1])
            col_src1.markdown(f"📄 **{sname}** (`.{stype}`) — **{scount}** bản ghi • Nạp lúc: `{sdate}`")

            # Nút tái lập chỉ mục nguồn (Re-index Source)
            if col_src2.button("🔄 Reindex", key=f"reindex_{sid}", help=f"Tái lập vector ChromaDB cho {sname}"):
                with st.spinner(f"Đang tái lập chỉ mục cho {sname}..."):
                    res = batch_manager.reindex_source(sid)
                    st.success(res["message"])
                    st.rerun()

            # Nút xóa nguồn (Delete Source)
            if col_src3.button("🗑️ Xóa Nguồn", key=f"del_{sid}", help=f"Xóa hoàn toàn dữ liệu của {sname} khỏi ChromaDB và BM25"):
                with st.spinner(f"Đang xóa nguồn {sname}..."):
                    del_res = batch_manager.delete_source(sid)
                    new_records = batch_manager.loader.load_from_jsonl()
                    engine.update_knowledge_base(new_records)
                    st.success(del_res["message"])
                    st.toast(f"Đã xóa nguồn {sname}!", icon="🗑️")
                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# Chân trang chuẩn demo.png
st.markdown(
    """
    <div style="text-align: center; color: #94A3B8; font-size: 0.85rem; margin-top: 36px; margin-bottom: 16px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        Built with Gradio 🧡
    </div>
    """,
    unsafe_allow_html=True
)

