"""Module giao tiếp với dịch vụ Ollama cục bộ (Localhost).

Thực hiện gọi API http://localhost:11434/api/chat qua HTTP,
xử lý lỗi kết nối, timeout và hỗ trợ sinh chuỗi phản hồi (streaming).
"""

import json
import logging
import re
from typing import Dict, Iterator, List, Optional

import requests

from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama

from config.settings import settings
from src.core.exceptions import OllamaConnectionError, OllamaResponseError
from src.llm.prompts import get_langchain_prompt_template

logger = logging.getLogger(__name__)


def clean_chinese_characters(text: str) -> str:
    """Loại bỏ triệt để các ký tự chữ Hán / tiếng Trung nếu mô hình vô tình sinh ra."""
    if not text:
        return ""
    # Biểu thức chính quy phát hiện dải ký tự Hán CJK (\u4e00 - \u9fff)
    cleaned = re.sub(r"[\u4e00-\u9fff]+", "", text)
    return cleaned.strip()



class OllamaClient:
    """Client giao tiếp HTTP với Ollama trên localhost."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT_SECONDS
        self.chat_endpoint = f"{self.base_url}/api/chat"

    def is_service_ready(self) -> bool:
        """Kiểm tra dịch vụ Ollama có đang hoạt động trên máy tính không."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False

    def chat(self, messages: List[Dict[str, str]], temperature: Optional[float] = None) -> str:
        """Gửi yêu cầu chat đồng bộ và nhận kết quả hoàn chỉnh."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else settings.LLM_TEMPERATURE
            }
        }

        try:
            resp = requests.post(
                self.chat_endpoint,
                json=payload,
                timeout=self.timeout
            )
            if resp.status_code != 200:
                raise OllamaResponseError(
                    f"Ollama trả về mã lỗi HTTP {resp.status_code}: {resp.text}"
                )
            data = resp.json()
            raw_content = data.get("message", {}).get("content", "")
            return clean_chinese_characters(raw_content)

        except requests.exceptions.ConnectionError as err:
            logger.error("Không thể kết nối tới Ollama tại %s: %s", self.chat_endpoint, err)
            raise OllamaConnectionError(settings.OLLAMA_OFFLINE_RESPONSE) from err
        except requests.exceptions.Timeout as err:
            logger.error("Yêu cầu tới Ollama bị timeout sau %.1f giây", self.timeout)
            raise OllamaResponseError("Mô hình xử lý quá thời gian quy định.") from err
        except Exception as err:
            logger.error("Lỗi không xác định khi gọi Ollama: %s", err)
            raise OllamaResponseError(f"Lỗi khi giao tiếp với Ollama: {err}") from err

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None
    ) -> Iterator[str]:
        """Gửi yêu cầu chat và trả về luồng sinh từ (stream tokens) cho giao diện UI."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature if temperature is not None else settings.LLM_TEMPERATURE
            }
        }

        try:
            with requests.post(
                self.chat_endpoint,
                json=payload,
                timeout=self.timeout,
                stream=True
            ) as resp:
                if resp.status_code != 200:
                    raise OllamaResponseError(
                        f"Ollama trả về mã lỗi HTTP {resp.status_code}: {resp.text}"
                    )

                for line in resp.iter_lines(decode_unicode=True):
                    if line:
                        chunk_json = json.loads(line)
                        token = chunk_json.get("message", {}).get("content", "")
                        # Lọc ký tự tiếng Trung ngay trong từng chunk
                        filtered_token = clean_chinese_characters(token)
                        if filtered_token:
                            yield filtered_token

        except requests.exceptions.ConnectionError as err:
            logger.error("Không thể kết nối tới Ollama khi stream: %s", err)
            raise OllamaConnectionError(settings.OLLAMA_OFFLINE_RESPONSE) from err
        except Exception as err:
            logger.error("Lỗi trong quá trình streaming từ Ollama: %s", err)
            raise OllamaResponseError(f"Lỗi streaming từ Ollama: {err}") from err

    def get_langchain_model(self) -> ChatOllama:
        """Khởi tạo đối tượng ChatOllama của LangChain kết nối dịch vụ Ollama cục bộ."""
        return ChatOllama(
            model=self.model,
            base_url=self.base_url,
            temperature=settings.LLM_TEMPERATURE
        )

    def generate_with_langchain(self, question: str, context: str) -> str:
        """Sử dụng LangChain LCEL Chain (PromptTemplate | ChatOllama | StrOutputParser) để sinh câu trả lời RAG."""
        try:
            prompt_tmpl = get_langchain_prompt_template()
            llm = self.get_langchain_model()
            chain = prompt_tmpl | llm | StrOutputParser()
            raw_text = chain.invoke({"question": question, "context": context})
            return clean_chinese_characters(raw_text)
        except Exception as err:
            logger.error("Lỗi khi thực thi LangChain LCEL RAG chain: %s", err)
            raise OllamaResponseError(f"Lỗi LangChain: {err}") from err

