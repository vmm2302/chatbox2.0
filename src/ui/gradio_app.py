"""Module giao diện người dùng Gradio đồng bộ 100% từ rag-chatbot-main.

Giao diện trực quan mô phỏng chính xác phong cách thiết kế từ assets/demo.png:
- Soft Slate theme (#64748B, #FF7373)
- 3 Tabs chính: Interface, Setting, Output (+ Quản Trị Kho Tri Thức)
- Cột trái: Status ("Ready!", "Answering!", "Completed!"), Language radio, Choose Model dropdown, Add Documents
- Cột phải: Chatbot card với bubble layout, avatar user.png & bot.png, inline dropdown Mode ("QA", "chat"), Textbox và 4 nút (Hide Setting, Undo, Clear, Reset)
- Tích hợp 100% logic backend local: Qwen2.5:7B, PhoBERT intent, BGE-M3 + BM25 RRF, Topic Tracker, Batch Ingestion.
"""

import os
import sys
import time
import json
import shutil
from pathlib import Path
from typing import List, Dict, Any, Generator, Tuple

import gradio as gr

# Xác định đường dẫn gốc của dự án
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from src.core.models import ChatResponse, RetrievalResult
from src.chat.engine import ChatEngine
from src.data.batch_ingestion import BatchIngestionManager, BatchStatus, FileStatus
from src.llm.prompts import SYSTEM_PROMPT

# Assets đường dẫn Avatar
USER_AVATAR = str(PROJECT_ROOT / "assets" / "user.png")
BOT_AVATAR = str(PROJECT_ROOT / "assets" / "bot.png")

# CSS và JS chuẩn hóa từ rag-chatbot-main/ui/theme.py
JS_LIGHT_THEME = """
function refresh() {
    const url = new URL(window.location);
    if (url.searchParams.get('__theme') !== 'light') {
        url.searchParams.set('__theme', 'light');
        window.location.href = url.href;
    }
}
"""

CUSTOM_CSS = """
.btn {
    background-color: #64748B !important;
    color: #FFFFFF !important;
}

.stop_btn {
    background-color: #FF7373 !important;
    color: #FFFFFF !important;
}

/* Tinh chỉnh typography và viền mềm chuẩn rag-chatbot-main */
.gradio-container {
    max-width: 1280px !important;
    margin: 0 auto !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
}

/* Đảm bảo bong bóng người dùng luôn ở BÊN PHẢI (User message on the RIGHT) */
.bubble.user-row, .user-row, div[data-testid="user"] {
    display: flex !important;
    flex-direction: row !important;
    justify-content: flex-end !important;
    align-self: flex-end !important;
    margin-left: auto !important;
    margin-right: 0 !important;
}

.user-row > .avatar-container, div[data-testid="user"] > .avatar-container {
    order: 2 !important;
    margin-left: 12px !important;
    margin-right: 0 !important;
}

.user, .message.user, div[data-testid="user"] .message {
    align-self: flex-end !important;
    background-color: #F1F5F9 !important;
    color: #0F172A !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 18px 18px 4px 18px !important;
    padding: 10px 16px !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05) !important;
    text-align: left !important;
}

/* Đảm bảo bong bóng Chatbot luôn ở BÊN TRÁI (Chatbot message on the LEFT) */
.bubble.bot-row, .bot-row, div[data-testid="bot"] {
    display: flex !important;
    flex-direction: row !important;
    justify-content: flex-start !important;
    align-self: flex-start !important;
    margin-right: auto !important;
    margin-left: 0 !important;
}

.bot-row > .avatar-container, div[data-testid="bot"] > .avatar-container {
    order: 0 !important;
    margin-right: 12px !important;
    margin-left: 0 !important;
}

.bot, .message.bot, div[data-testid="bot"] .message {
    align-self: flex-start !important;
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 18px 18px 18px 4px !important;
    padding: 12px 18px !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05) !important;
    text-align: left !important;
}
"""

# Khởi tạo singleton ChatEngine và BatchIngestionManager
_engine = None
_batch_manager = None
_audit_logs: List[Dict[str, Any]] = []


def get_engine() -> ChatEngine:
    global _engine
    if _engine is None:
        _engine = ChatEngine()
    return _engine


def get_batch_manager() -> BatchIngestionManager:
    global _batch_manager
    if _batch_manager is None:
        _batch_manager = BatchIngestionManager()
    return _batch_manager


def create_gradio_app() -> gr.Blocks:
    """Xây dựng ứng dụng Gradio đồng bộ toàn diện với rag-chatbot-main."""
    engine = get_engine()
    batch_manager = get_batch_manager()

    theme = gr.themes.Soft(primary_hue="slate")

    with gr.Blocks(
        title="Local RAG Chatbot 🤖 - English Vocabulary Assistant"
    ) as demo:
        # Header chính
        gr.Markdown("## Local RAG Chatbot 🤖")

        # ======================================================================
        # TAB 1: INTERFACE (Giao diện chính chuẩn demo.png)
        # ======================================================================
        with gr.Tab("Interface"):
            sidebar_state = gr.State(True)

            with gr.Row(equal_height=False):
                # --- CỘT TRÁI: SETTING PANEL ---
                with gr.Column(scale=10, visible=True) as setting_col:
                    status_box = gr.Textbox(
                        label="Status",
                        value="Ready!",
                        interactive=False
                    )

                    lang_radio = gr.Radio(
                        label="Language",
                        choices=["vi", "eng"],
                        value="vi",
                        interactive=True
                    )

                    pipeline_indicator = gr.Dropdown(
                        label="Pipeline Trình Tự Cố Định:",
                        choices=[
                            "PhoBERT ➔ BM25 + BGE-M3 ➔ RRF Gate ➔ Qwen2.5:7B"
                        ],
                        value="PhoBERT ➔ BM25 + BGE-M3 ➔ RRF Gate ➔ Qwen2.5:7B",
                        interactive=False,
                        info="Ba mô hình thực thi tuần tự trong 1 pipeline duy nhất (không chọn thay thế)."
                    )

                    doc_files = gr.Files(
                        label="Add Documents",
                        value=[],
                        file_types=[".txt", ".pdf", ".csv", ".xlsx", ".docx", ".json", ".jsonl", ".md"],
                        file_count="multiple",
                        height=160
                    )

                    with gr.Row():
                        upload_doc_btn = gr.Button("Upload", elem_classes=["btn"])
                        reset_doc_btn = gr.Button("Reset", elem_classes=["stop_btn"])

                    # Giám sát thông tin ngữ cảnh & PhoBERT
                    active_word_display = gr.Markdown("🎯 **Active Topic:** `Chưa có`")

                # --- CỘT PHẢI: CHATBOT VIEWPORT ---
                with gr.Column(scale=30):
                    chatbot = gr.Chatbot(
                        label="Chatbot",
                        layout="bubble",
                        value=[{
                            "role": "assistant",
                            "content": "Hi 👋, how can I help you today? Tôi là trợ lý tra cứu từ vựng tiếng Anh. Bạn có thể hỏi bất kỳ từ vựng nào bằng tiếng Việt tự nhiên!"
                        }],
                        height=550,
                        avatar_images=(USER_AVATAR, BOT_AVATAR),
                        buttons=["copy"]
                    )

                    # Hàng nhập liệu inline: [QA / chat] + [Enter you message:]
                    with gr.Row():
                        chat_mode = gr.Dropdown(
                            choices=["QA", "chat"],
                            value="QA",
                            min_width=70,
                            show_label=False,
                            interactive=True,
                            scale=1
                        )
                        message_input = gr.MultimodalTextbox(
                            value={"text": ""},
                            placeholder="Enter you message:",
                            file_types=[".txt", ".pdf", ".csv", ".xlsx", ".docx", ".json"],
                            show_label=False,
                            scale=6,
                            lines=1
                        )

                    # Hàng 4 nút chuẩn rag-chatbot-main: Hide Setting, Undo, Clear, Reset
                    with gr.Row():
                        hide_setting_btn = gr.Button(value="Hide Setting", min_width=20)
                        undo_btn = gr.Button(value="Undo", min_width=20)
                        clear_btn = gr.Button(value="Clear", min_width=20)
                        reset_btn = gr.Button(value="Reset", min_width=20, elem_classes=["stop_btn"])

        # ======================================================================
        # TAB 2: SETTING
        # ======================================================================
        with gr.Tab("Setting"):
            system_prompt_box = gr.Textbox(
                label="System Prompt",
                value=SYSTEM_PROMPT,
                interactive=True,
                lines=12,
                max_lines=40
            )
            with gr.Row():
                set_prompt_btn = gr.Button(value="Set System Prompt", elem_classes=["btn"])
                reset_prompt_btn = gr.Button(value="Reset to Default Prompt")

            with gr.Row():
                gr.Slider(label="Temperature LLM (Độ sáng tạo)", minimum=0.0, maximum=1.0, value=settings.LLM_TEMPERATURE, step=0.05, interactive=False)
                gr.Number(label="RRF Smoothing Parameter (k)", value=settings.RRF_K, interactive=False)
                gr.Number(label="Top-K Retrieval Candidates", value=settings.TOP_K_RETRIEVAL, interactive=False)

        # ======================================================================
        # TAB 3: OUTPUT (System Logs & Audit Trace)
        # ======================================================================
        with gr.Tab("Output"):
            with gr.Row():
                audit_code_view = gr.Code(
                    label="Audit Log Trace",
                    language="markdown",
                    interactive=False,
                    lines=28
                )
            with gr.Row():
                refresh_log_btn = gr.Button("🔄 Làm Mới Nhật Ký", elem_classes=["btn"])
                clear_log_btn = gr.Button("🧹 Xóa Nhật Ký")

        # ======================================================================
        # TAB 4: QUẢN TRỊ KHO TRI THỨC (Batch Ingestion Admin)
        # ======================================================================
        with gr.Tab("📁 Quản Trị Kho Tri Thức"):
            gr.Markdown("### Quản trị nạp tài liệu hàng loạt (Batch Multi-File Ingestion)")
            batch_uploader = gr.Files(
                label="Kéo thả hoặc duyệt nhiều tệp từ máy tính:",
                file_types=[".pdf", ".docx", ".txt", ".csv", ".xlsx", ".json", ".jsonl", ".md"],
                file_count="multiple"
            )
            process_batch_btn = gr.Button("🚀 Bắt Đầu Xử Lý Tất Cả Tệp", elem_classes=["btn"])
            batch_report_markdown = gr.Markdown("Chưa có batch nào được xử lý.")

        # ======================================================================
        # CALLBACK HANDLERS
        # ======================================================================

        def generate_audit_markdown() -> str:
            if not _audit_logs:
                return "# CHATBOX 2.0 AUDIT LOG TRACE\n\nChưa có nhật ký truy vấn nào trong phiên hiện tại."
            lines = ["# CHATBOX 2.0 AUDIT LOG TRACE", f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"]
            for idx, entry in enumerate(reversed(_audit_logs), 1):
                lines.append(
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
            return "\n".join(lines)

        def handle_user_query(
            msg: Any,
            history: List[Dict[str, str]],
            mode: str
        ) -> Generator[Tuple[Dict[str, str], List[Dict[str, str]], str, str, str], None, None]:
            # Lấy chuỗi truy vấn từ multimodal dict hoặc str
            query = ""
            if isinstance(msg, dict):
                query = msg.get("text", "").strip()
            elif isinstance(msg, str):
                query = msg.strip()

            if not query:
                yield {"text": ""}, history, "Ready!", f"🎯 **Active Topic:** `{engine.tracker.active_word or 'Chưa có'}`", generate_audit_markdown()
                return

            # Ghi nhận tin nhắn người dùng
            new_history = list(history)
            new_history.append({"role": "user", "content": query})
            new_history.append({"role": "assistant", "content": ""})

            yield {"text": ""}, new_history, "Answering!", f"🎯 **Active Topic:** `{engine.tracker.active_word or 'Chưa có'}`", generate_audit_markdown()

            # Gọi RAG Pipeline của ChatEngine
            resp: ChatResponse = engine.ask(query)
            full_ans = resp.answer

            # Ghi nhật ký kiểm toán
            _audit_logs.append({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "query": query,
                "mode": resp.mode,
                "intent": resp.intent,
                "active_word": engine.tracker.active_word,
                "record_id": resp.record_id,
                "rrf_score": resp.rrf_score,
                "latency_ms": resp.latency_ms,
                "answer": resp.answer
            })

            # Hiệu ứng stream từng chữ
            step = max(1, len(full_ans) // 30)
            for i in range(1, len(full_ans) + 1, step):
                new_history[-1]["content"] = full_ans[:i]
                yield {"text": ""}, new_history, "Answering!", f"🎯 **Active Topic:** `{engine.tracker.active_word or 'Chưa có'}`", generate_audit_markdown()
                time.sleep(0.01)

            new_history[-1]["content"] = full_ans
            yield {"text": ""}, new_history, "Completed!", f"🎯 **Active Topic:** `{engine.tracker.active_word or 'Chưa có'}`", generate_audit_markdown()

        def handle_undo(history: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], str]:
            if history:
                if history and history[-1]["role"] == "assistant":
                    history.pop()
                if history and history[-1]["role"] == "user":
                    history.pop()
                if engine.tracker.history:
                    engine.tracker.history.pop()
                    engine.tracker.active_word = engine.tracker.history[-1].active_word if engine.tracker.history else None
            active_str = f"🎯 **Active Topic:** `{engine.tracker.active_word or 'Chưa có'}`"
            return history, active_str

        def handle_clear() -> Tuple[Dict[str, str], List[Dict[str, str]], str]:
            return {"text": ""}, [], "Ready!"

        def handle_reset() -> Tuple[Dict[str, str], List[Dict[str, str]], List, str, str]:
            engine.tracker.clear()
            welcome = [{
                "role": "assistant",
                "content": "Hi 👋, how can I help you today? Tôi là trợ lý tra cứu từ vựng tiếng Anh. Bạn có thể hỏi bất kỳ từ vựng nào bằng tiếng Việt tự nhiên!"
            }]
            return {"text": ""}, welcome, [], "Ready!", "🎯 **Active Topic:** `Chưa có`"

        def handle_toggle_setting(current_state: bool) -> Tuple[str, Any, bool]:
            new_state = not current_state
            btn_text = "Hide Setting" if new_state else "Show Setting"
            return btn_text, gr.update(visible=new_state), new_state

        def handle_doc_upload(files: List[Any]) -> str:
            if not files:
                return "Chưa chọn tệp tài liệu nào!"
            settings.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
            saved_paths: List[Path] = []
            for item in files:
                p_str = item if isinstance(item, str) else getattr(item, "name", str(item))
                src_p = Path(p_str)
                dst_p = settings.RAW_DATA_DIR / src_p.name
                if src_p != dst_p:
                    shutil.copy2(src_p, dst_p)
                saved_paths.append(dst_p)

            rep = batch_manager.ingest_batch(saved_paths)
            new_records = batch_manager.loader.load_from_jsonl()
            engine.update_knowledge_base(new_records)
            return f"Processing documents completed! Added {rep.total_records_added} records."

        def handle_batch_process(files: List[Any]) -> str:
            if not files:
                return "⚠️ Vui lòng chọn ít nhất 1 tệp!"
            settings.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
            saved_paths = []
            for item in files:
                p_str = item if isinstance(item, str) else getattr(item, "name", str(item))
                src_p = Path(p_str)
                dst_p = settings.RAW_DATA_DIR / src_p.name
                if src_p != dst_p:
                    shutil.copy2(src_p, dst_p)
                saved_paths.append(dst_p)

            rep = batch_manager.ingest_batch(saved_paths)
            new_records = batch_manager.loader.load_from_jsonl()
            engine.update_knowledge_base(new_records)

            md = f"""
### 🎉 Kết Quả Xử Lý Batch: `{rep.batch_status.value}`
* **Tổng số tệp:** {rep.total_files} | **Thành công:** {rep.success_count} | **Bỏ qua:** {rep.skipped_count} | **Lỗi:** {rep.failed_count}
* **Bản ghi nạp mới:** `+{rep.total_records_added:,}` cặp Q&A
* **Thời gian xử lý:** `{rep.total_elapsed_seconds:.2f}` giây
"""
            return md

        # Kết nối sự kiện tương tác
        message_input.submit(
            handle_user_query,
            inputs=[message_input, chatbot, chat_mode],
            outputs=[message_input, chatbot, status_box, active_word_display, audit_code_view]
        )

        undo_btn.click(
            handle_undo,
            inputs=[chatbot],
            outputs=[chatbot, active_word_display]
        )

        clear_btn.click(
            handle_clear,
            outputs=[message_input, chatbot, status_box]
        )

        reset_btn.click(
            handle_reset,
            outputs=[message_input, chatbot, doc_files, status_box, active_word_display]
        )

        hide_setting_btn.click(
            handle_toggle_setting,
            inputs=[sidebar_state],
            outputs=[hide_setting_btn, setting_col, sidebar_state]
        )

        upload_doc_btn.click(
            handle_doc_upload,
            inputs=[doc_files],
            outputs=[status_box]
        )

        reset_doc_btn.click(
            lambda: ([], "Ready!"),
            outputs=[doc_files, status_box]
        )

        refresh_log_btn.click(
            generate_audit_markdown,
            outputs=[audit_code_view]
        )

        clear_log_btn.click(
            lambda: (_audit_logs.clear(), "# CHATBOX 2.0 AUDIT LOG TRACE\n\nNhật ký đã được làm sạch."),
            outputs=[gr.State(), audit_code_view]
        )

        process_batch_btn.click(
            handle_batch_process,
            inputs=[batch_uploader],
            outputs=[batch_report_markdown]
        )

    return demo


def main():
    """Khởi chạy máy chủ Gradio trên cổng 7860."""
    app = create_gradio_app()
    print("Khởi chạy giao diện Gradio tại http://localhost:7860 ...")
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        theme=gr.themes.Soft(primary_hue="slate"),
        css=CUSTOM_CSS,
        js=JS_LIGHT_THEME
    )


if __name__ == "__main__":
    main()
