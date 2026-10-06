"""Kiểm thử tích hợp đầu cuối (End-to-End Integration Test) với toàn bộ 3,725 bản ghi thật."""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.core.chatbot import ChatbotEngine


def run_e2e_test():
    print("=" * 60)
    print("BẮT ĐẦU END-TO-END INTEGRATION TEST VỚI DATASET THẬT (3,725 BẢN GHI)")
    print("=" * 60)

    engine = ChatbotEngine()
    engine.warm_up()

    test_queries = [
        # 1. Exact match tra từ vựng
        ("about nghĩa là gì?", "DIRECT_MATCH"),
        # 2. Câu hỏi tự nhiên khớp từ vựng
        ("cho mình hỏi từ about có nghĩa là gì vậy?", "DIRECT_MATCH"),
        # 3. Câu hỏi tra câu ví dụ
        ("Cho tôi câu ví dụ của từ about này.", "DIRECT_MATCH"),
        # 4. Câu hỏi danh sách theo trình độ
        ("Cho tôi 1 danh sách gồm các từ tiếng anh trong trình độ A1", "DIRECT_MATCH"),
        # 5. Câu hỏi tổng hợp đòi hỏi Qwen2.5:7B diễn đạt (RAG Generation)
        ("từ about dùng như thế nào và có những ví dụ nào?", "RAG_GENERATION"),
        # 6. Câu hỏi ngoài phạm vi tri thức (Địa lý)
        ("Thủ đô của nước Pháp là gì?", "NO_MATCH"),
        # 7. Câu hỏi ngoài phạm vi tri thức (Thời tiết)
        ("Thời tiết tại Hà Nội ngày mai thế nào?", "NO_MATCH")
    ]

    all_passed = True
    for q, expected_mode in test_queries:
        print(f"\n[QUERY]: {q}")
        resp = engine.ask(q)
        print(f"-> Mode: {resp.mode} (Expected: {expected_mode})")
        print(f"-> Score: {resp.confidence_score:.3f}")
        print(f"-> Record ID: {resp.matched_record_id}")
        print(f"-> Latency: {resp.processing_time_ms} ms")
        print(f"-> Answer:\n{resp.answer[:200]}...")

        if resp.mode != expected_mode:
            print(f"[THẤT BẠI]: Kỳ vọng {expected_mode} nhưng nhận {resp.mode}")
            all_passed = False
        else:
            print("[THÀNH CÔNG]")

    print("\n" + "=" * 60)
    if all_passed:
        print("TẤT CẢ CÁC TEST CASES ĐÃ ĐẠT 100% KỲ VỌNG!")
    else:
        print("CÓ TEST CASE CHƯA ĐẠT.")
    print("=" * 60)


if __name__ == "__main__":
    run_e2e_test()
