"""Module điều phối Chatbot kế thừa toàn diện từ Master Architecture ChatEngine.

Cung cấp lớp ChatbotEngine tương thích ngược hoàn toàn với các phiên bản trước đó.
"""

from typing import Generator, List, Optional, Tuple

from src.chat.engine import ChatEngine
from src.core.models import ChatResponse, QARecord
from src.llm.client import OllamaClient
from src.retriever.hybrid_retriever import HybridRetriever


class ChatbotEngine(ChatEngine):
    """Wrapper tương thích ngược kế thừa từ ChatEngine mới."""

    def __init__(
        self,
        records: Optional[List[QARecord]] = None,
        retriever: Optional[HybridRetriever] = None,
        llm_client: Optional[OllamaClient] = None
    ):
        super().__init__(
            records=records,
            retriever=retriever,
            llm_client=llm_client
        )
