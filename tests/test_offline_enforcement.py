"""Kiểm thử tuân thủ chế độ Offline nghiêm ngặt (Strict Offline Enforcement Test Suite).

Kiểm tra:
1. Khi thiếu cache mô hình BGE-M3 trong local storage:
   - Hệ thống ném RuntimeError kèm thông điệp hướng dẫn rõ ràng.
   - Tuyệt đối không tự ý gỡ biến HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE để gọi Internet trong runtime.
2. Khi thiếu cache mô hình PhoBERT trong local storage:
   - Hệ thống ném RuntimeError kèm thông điệp hướng dẫn rõ ràng.
   - Tuyệt đối không tự ý gỡ biến offline trong runtime.
"""

import os
import unittest
from unittest.mock import patch

from src.nlp.phobert_intent import PhoBERTIntentClassifier
from src.retriever.bge_chroma import BGEChromaRetriever


class TestOfflineEnforcement(unittest.TestCase):
    """Kiểm tra không tải model qua mạng trong thời gian chạy (runtime)."""

    def setUp(self):
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"

    @patch("src.retriever.bge_chroma.SentenceTransformer")
    def test_bge_chroma_raises_error_without_popping_offline_env(self, mock_st):
        """Khi local cache của BGE-M3 thiếu, phải ném RuntimeError và giữ nguyên biến môi trường offline."""
        mock_st.side_effect = FileNotFoundError("Local model directory not found")

        retriever = BGEChromaRetriever(records=[])

        with self.assertRaises(RuntimeError) as ctx:
            retriever._get_embedding_model()

        # Thông điệp lỗi phải chỉ rõ hướng dẫn tải model trước
        err_text = str(ctx.exception)
        self.assertIn("OFFLINE", err_text)
        self.assertIn("download_models.py", err_text)

        # Biến môi trường offline không bao giờ bị xóa
        self.assertEqual(os.environ.get("HF_HUB_OFFLINE"), "1")
        self.assertEqual(os.environ.get("TRANSFORMERS_OFFLINE"), "1")

    @patch("src.nlp.phobert_intent.AutoTokenizer.from_pretrained")
    def test_phobert_raises_error_without_popping_offline_env(self, mock_tok):
        """Khi local cache của PhoBERT thiếu, phải ném RuntimeError và giữ nguyên biến môi trường offline."""
        mock_tok.side_effect = FileNotFoundError("Local checkpoint not found")

        classifier = PhoBERTIntentClassifier()

        with self.assertRaises(RuntimeError) as ctx:
            classifier.initialize()

        err_text = str(ctx.exception)
        self.assertIn("OFFLINE", err_text)
        self.assertIn("download_models.py", err_text)

        # Biến môi trường offline không bao giờ bị xóa
        self.assertEqual(os.environ.get("HF_HUB_OFFLINE"), "1")
        self.assertEqual(os.environ.get("TRANSFORMERS_OFFLINE"), "1")


if __name__ == "__main__":
    unittest.main()
