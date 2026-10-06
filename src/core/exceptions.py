"""Định nghĩa các ngoại lệ đặc thù của hệ thống Chatbox 2.0."""


class ChatboxException(Exception):
    """Ngoại lệ cơ sở cho toàn bộ hệ thống Chatbox 2.0."""
    pass


class OllamaConnectionError(ChatboxException):
    """Ngoại lệ khi không thể kết nối tới dịch vụ Ollama tại localhost."""
    pass


class OllamaResponseError(ChatboxException):
    """Ngoại lệ khi Ollama trả về lỗi hoặc định dạng không hợp lệ."""
    pass


class DataLoadError(ChatboxException):
    """Ngoại lệ khi quá trình tải hoặc kiểm tra dữ liệu gặp sự cố."""
    pass


class RetrievalError(ChatboxException):
    """Ngoại lệ khi tìm kiếm hoặc nạp chỉ mục dữ liệu gặp lỗi."""
    pass
