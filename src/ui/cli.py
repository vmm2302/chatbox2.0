"""Giao diện dòng lệnh (CLI Terminal) cho Chatbox 2.0.

Phục vụ việc kiểm thử nhanh, gỡ lỗi và đánh giá hiệu năng trực tiếp trên Terminal.
"""

import sys
from pathlib import Path

# Đảm bảo đường dẫn gốc được nhận diện khi chạy trực tiếp
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import settings
from src.core.chatbot import ChatbotEngine

# Đảm bảo in tiếng Việt trên console Windows không bị lỗi font
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main():
    print("=" * 60)
    print("     CHATBOX 2.0 - LOCAL QWEN2.5:7B (CLI TERMINAL)")
    print("=" * 60)
    print(f"Mô hình LLM: {settings.OLLAMA_MODEL} (Localhost)")
    print(f"Ngưỡng Direct Match: {settings.DIRECT_MATCH_THRESHOLD}")
    print(f"Ngưỡng RAG Generation: {settings.RAG_THRESHOLD}")
    print("Gõ 'exit' hoặc 'quit' để thoát.\n")

    engine = ChatbotEngine()
    engine.warm_up()
    print(f"Đã nạp thành công {len(engine.records):,} bản ghi Q&A.\n")

    while True:
        try:
            query = input("\nBạn: ").strip()
            if not query:
                continue
            if query.lower() in ["exit", "quit", "q"]:
                print("Tạm biệt!")
                break

            response = engine.ask(query)

            print(f"\n[AI - {response.mode} | Score: {response.confidence_score:.3f} | {response.processing_time_ms}ms]:")
            print(response.answer)

            if response.matched_record_id:
                print(f"-> Nguồn: [{response.matched_record_id}] {response.source}")

        except KeyboardInterrupt:
            print("\nĐã ngắt chương trình.")
            break
        except Exception as err:
            print(f"\n[Lỗi]: {err}")


if __name__ == "__main__":
    main()
