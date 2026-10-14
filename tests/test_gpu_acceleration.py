"""Unit tests for GPU Acceleration and dynamic device allocation in BGEChromaRetriever."""

import unittest
from unittest.mock import patch
import torch

from src.retriever.bge_chroma import BGEChromaRetriever
from config.settings import settings


class TestGPUAcceleration(unittest.TestCase):
    """Kiểm tra cơ chế tự động nhận diện và phân bổ GPU/CPU cho mô hình BGE-M3."""

    def setUp(self):
        self.retriever = BGEChromaRetriever([])
        self.original_dev = settings.EMBEDDING_DEVICE

    def tearDown(self):
        object.__setattr__(settings, "EMBEDDING_DEVICE", self.original_dev)

    def test_resolve_device_auto(self):
        """Khi EMBEDDING_DEVICE='auto', phải chọn 'cuda' nếu có CUDA, ngược lại 'cpu'."""
        object.__setattr__(settings, "EMBEDDING_DEVICE", "auto")
        dev = self.retriever._resolve_device()
        expected = "cuda" if torch.cuda.is_available() else "cpu"
        self.assertEqual(dev, expected)

    def test_resolve_device_explicit_cpu(self):
        """Khi cấu hình tường minh EMBEDDING_DEVICE='cpu', phải trả về 'cpu'."""
        object.__setattr__(settings, "EMBEDDING_DEVICE", "cpu")
        dev = self.retriever._resolve_device()
        self.assertEqual(dev, "cpu")

    def test_resolve_device_cuda_fallback_when_no_cuda(self):
        """Khi cấu hình EMBEDDING_DEVICE='cuda' nhưng mock không có CUDA, phải fallback về 'cpu'."""
        object.__setattr__(settings, "EMBEDDING_DEVICE", "cuda")
        with patch("torch.cuda.is_available", return_value=False):
            dev = self.retriever._resolve_device()
            self.assertEqual(dev, "cpu")

    def test_actual_hardware_cuda_availability(self):
        """Kiểm tra nhận diện phần cứng RTX 3050 thực tế trong môi trường."""
        if torch.cuda.is_available():
            dev = self.retriever._resolve_device()
            self.assertEqual(dev, "cuda")
            self.assertIn("RTX", torch.cuda.get_device_name(0).upper())


if __name__ == "__main__":
    unittest.main()
