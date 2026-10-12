"""Module giao diện người dùng Gradio cho Chatbox 2.0.

Thiết kế hiện đại, tinh gọn, tập trung 100% vào trải nghiệm người dùng chatbox:
- Giao diện Chatbot trung tâm với bong bóng chat trực quan, avatar người dùng và bot.
- Tự động ẩn hoàn toàn footer Gradio (Built with Gradio 🧡) và loại bỏ các phần tử thừa.
- Tích hợp 100% backend local: Qwen2.5:7B, PhoBERT, BGE-M3, BM25 Okapi, RRF Fusion.
- Quản trị kho tri thức và Cài đặt được tổ chức thành các tab riêng biệt, không làm phiền khung chat.
"""

import os
import sys
import time
import json
import shutil
from pathlib import Path
from typing import List, Dict, Any, Generator, Tuple

import gradio as gr

# Đảm bảo in tiếng Việt có dấu không bị lỗi UnicodeEncodeError trên Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Xác định đường dẫn gốc của dự án
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from src.core.models import ChatResponse
from src.chat.engine import ChatEngine
from src.data.batch_ingestion import BatchIngestionManager
from src.llm.prompts import SYSTEM_PROMPT

# Assets đường dẫn Avatar
USER_AVATAR = str(PROJECT_ROOT / "assets" / "user.png")
BOT_AVATAR = str(PROJECT_ROOT / "assets" / "bot.png")

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
/* Ẩn hoàn toàn footer mặc định của Gradio ('Built with Gradio') */
footer {
    display: none !important;
    visibility: hidden !important;
}

.gradio-container > footer {
    display: none !important;
}

.btn {
    background-color: #3B82F6 !important;
    color: #FFFFFF !important;
}

.btn:hover {
    background-color: #2563EB !important;
}

.stop_btn {
    background-color: #EF4444 !important;
    color: #FFFFFF !important;
}

/* Tinh chỉnh container chuẩn cho Chatbox */
.gradio-container {
    max-width: 1080px !important;
    margin: 0 auto !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
}

/* Đảm bảo bong bóng người dùng luôn ở BÊN PHẢI */
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
    background-color: #3B82F6 !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 18px 18px 4px 18px !important;
    padding: 10px 16px !important;
    box-shadow: 0 2px 4px rgba(59, 130, 246, 0.15) !important;
    text-align: left !important;
}

/* Đảm bảo bong bóng Chatbot luôn ở BÊN TRÁI */
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
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
    text-align: left !important;
}
"""

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
    """Xây dựng ứng dụng Gradio tinh gọn, tập trung vào Chatbox."""
    engine = get_engine()
    batch_manager = get_batch_manager()

    with gr.Blocks(
        title="Trợ Lý Từ Vựng Tiếng Anh 🤖 - Local RAG Chatbox"
    ) as demo:
        # Header chính
        gr.Markdown(
            "## Trợ Lý Từ Vựng Tiếng Anh 🤖\n"
            "*Tra cứu định nghĩa, phát âm, từ loại, ví dụ và ngữ cảnh bằng tiếng Việt tự nhiên (100% Local AI)*"
        )

        # ======================================================================
        # TAB 1: 💬 CHATBOX (GIAO DIỆN CHÍNH TINH GỌN)
        # ======================================================================
        with gr.Tab("💬 Chatbox"):
            active_word_display = gr.Markdown("🎯 **Chủ đề đang mở:** `Chưa có`")

            chatbot = gr.Chatbot(
                label="Hội Thoại Từ Vựng",
                layout="bubble",
                value=[{
                    "role": "assistant",
                    "content": "Hi 👋, how can I help you today? Tôi là trợ lý tra cứu từ vựng tiếng Anh chạy 100% cục bộ. Bạn có thể hỏi bất kỳ từ vựng nào bằng tiếng Việt tự nhiên!"
                }],
                height=560,
                avatar_images=(USER_AVATAR, BOT_AVATAR),
                buttons=["copy"]
            )

            with gr.Row():
                message_input = gr.Textbox(
                    placeholder="Nhập câu hỏi hoặc từ vựng cần tra cứu... (Ví dụ: 'abandon là gì?', 'ví dụ từ resilient')",
                    show_label=False,
                    scale=8,
                    lines=1
                )
                send_btn = gr.Button("Gửi ➤", elem_classes=["btn"], scale=1)

            # Hàng nút tác vụ tiện ích
            with gr.Row():
                undo_btn = gr.Button(value="↩️ Hoàn Tác Lượt Trước", min_width=20)
                clear_btn = gr.Button(value="🧹 Xóa Đoạn Chat", min_width=20)
                reset_btn = gr.Button(value="🔄 Cuộc Trò Chuyện Mới", min_width=20, elem_classes=["stop_btn"])

        # ======================================================================
        # TAB 2: 📁 QUẢN TRỊ KHO TRI THỨC (BATCH INGESTION)
        # ======================================================================
        with gr.Tab("📁 Quản Trị Kho Tri Thức"):
            gr.Markdown("### Nạp tài liệu vào kho tri thức (Batch Multi-File Ingestion)")
            batch_mode = gr.Radio(
                label="Chế độ nạp (Import Mode):",
                choices=["ADD", "REPLACE"],
                value="ADD",
                info="ADD: Bổ sung mới / Cập nhật trùng ID. REPLACE: Xóa toàn bộ DB cũ và nạp lại từ các tệp này."
            )
            batch_uploader = gr.Files(
                label="Kéo thả hoặc chọn nhiều tệp (.pdf, .docx, .txt, .csv, .xlsx, .json, .md):",
                file_types=[".pdf", ".docx", ".txt", ".csv", ".xlsx", ".json", ".jsonl", ".md"],
                file_count="multiple"
            )
            process_batch_btn = gr.Button("🚀 Bắt Đầu Xử Lý Tất Cả Tệp", elem_classes=["btn"])
            batch_report_markdown = gr.Markdown("Chưa có batch nào được xử lý.")

        # ======================================================================
        # TAB 3: ⚙️ CÀI ĐẶT & NHẬT KÝ (SETTING & AUDIT LOGS)
        # ======================================================================
        with gr.Tab("⚙️ Cài Đặt & Nhật Ký"):
            with gr.Accordion("Cấu Hình System Prompt", open=False):
                system_prompt_box = gr.Textbox(
                    label="System Prompt",
                    value=SYSTEM_PROMPT,
                    interactive=True,
                    lines=10,
                    max_lines=30
                )
                with gr.Row():
                    set_prompt_btn = gr.Button(value="Lưu System Prompt", elem_classes=["btn"])
                    reset_prompt_btn = gr.Button(value="Khôi Phục Mặc Định")

            with gr.Accordion("Nhật Ký Truy Vấn (Audit Log Trace)", open=True):
                audit_code_view = gr.Code(
                    label="Audit Log Trace",
                    language="markdown",
                    interactive=False,
                    lines=20
                )
                with gr.Row():
                    refresh_log_btn = gr.Button("🔄 Làm Mới Nhật Ký", elem_classes=["btn"])
                    clear_log_btn = gr.Button("🧹 Xóa Nhật Ký")

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
            query_str: str,
            history: List[Dict[str, str]]
        ) -> Generator[Tuple[str, List[Dict[str, str]], str, str], None, None]:
            query = query_str.strip() if query_str else ""
            if not query:
                yield "", history, f"🎯 **Chủ đề đang mở:** `{engine.tracker.active_word or 'Chưa có'}`", generate_audit_markdown()
                return

            new_history = list(history)
            new_history.append({"role": "user", "content": query})
            new_history.append({"role": "assistant", "content": ""})

            yield "", new_history, f"🎯 **Chủ đề đang mở:** `{engine.tracker.active_word or 'Chưa có'}`", generate_audit_markdown()

            resp: ChatResponse = engine.ask(query)
            full_ans = resp.answer

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

            step = max(1, len(full_ans) // 30)
            for i in range(1, len(full_ans) + 1, step):
                new_history[-1]["content"] = full_ans[:i]
                yield "", new_history, f"🎯 **Chủ đề đang mở:** `{engine.tracker.active_word or 'Chưa có'}`", generate_audit_markdown()
                time.sleep(0.01)

            new_history[-1]["content"] = full_ans
            yield "", new_history, f"🎯 **Chủ đề đang mở:** `{engine.tracker.active_word or 'Chưa có'}`", generate_audit_markdown()

        def handle_undo(history: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], str]:
            if history:
                if history and history[-1]["role"] == "assistant":
                    history.pop()
                if history and history[-1]["role"] == "user":
                    history.pop()
                if engine.tracker.history:
                    engine.tracker.history.pop()
                    engine.tracker.active_word = engine.tracker.history[-1].active_word if engine.tracker.history else None
            active_str = f"🎯 **Chủ đề đang mở:** `{engine.tracker.active_word or 'Chưa có'}`"
            return history, active_str

        def handle_clear() -> List[Dict[str, str]]:
            return []

        def handle_reset() -> Tuple[List[Dict[str, str]], str]:
            engine.tracker.clear()
            welcome = [{
                "role": "assistant",
                "content": "Hi 👋, how can I help you today? Tôi là trợ lý tra cứu từ vựng tiếng Anh chạy 100% cục bộ. Bạn có thể hỏi bất kỳ từ vựng nào bằng tiếng Việt tự nhiên!"
            }]
            return welcome, "🎯 **Chủ đề đang mở:** `Chưa có`"

        def handle_batch_process(files: List[Any], mode: str = "ADD") -> str:
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

            rep = batch_manager.ingest_batch(saved_paths, mode=mode.lower())
            new_records = batch_manager.loader.load_from_jsonl()
            engine.update_knowledge_base(new_records)

            md = f"""
### 🎉 Kết Quả Xử Lý Batch ({mode.upper()}): `{rep.batch_status.value}`
* **Tổng số tệp:** {rep.total_files} | **Thành công:** {rep.success_count} | **Bỏ qua:** {rep.skipped_count} | **Lỗi:** {rep.failed_count}
* **Bản ghi nạp mới/cập nhật:** `+{rep.total_records_added:,}` cặp Q&A
* **Thời gian xử lý:** `{rep.elapsed_seconds:.2f}` giây
"""
            return md

        # Kết nối sự kiện
        message_input.submit(
            handle_user_query,
            inputs=[message_input, chatbot],
            outputs=[message_input, chatbot, active_word_display, audit_code_view]
        )

        send_btn.click(
            handle_user_query,
            inputs=[message_input, chatbot],
            outputs=[message_input, chatbot, active_word_display, audit_code_view]
        )

        undo_btn.click(
            handle_undo,
            inputs=[chatbot],
            outputs=[chatbot, active_word_display]
        )

        clear_btn.click(
            handle_clear,
            outputs=[chatbot]
        )

        reset_btn.click(
            handle_reset,
            outputs=[chatbot, active_word_display]
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
            inputs=[batch_uploader, batch_mode],
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
