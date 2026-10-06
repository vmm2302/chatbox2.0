"""Module xử lý các ý định ngoại lệ, chào hỏi và giao tiếp xã giao (Exception & Chitchat Handler).

Kế thừa từ SmallTalkHandler để duy trì tính tương thích ngược cho hệ thống.
"""

from src.chat.small_talk_handler import SmallTalkHandler


class ExceptionHandler(SmallTalkHandler):
    """Lớp bọc tương thích ngược cho SmallTalkHandler."""
    pass
