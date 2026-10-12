"""Theme và CSS tùy biến cho giao diện Chatbox 2.0 (Streamlit).

Thiết kế giao diện hiện đại, tinh gọn, tập trung 100% vào trải nghiệm người dùng chatbox:
- Khung container 1280px rộng rãi, bố cục 2 cột linh hoạt (Cột Cài đặt bên trái + Khung Chat bên phải).
- Bật/tắt bảng Cài đặt bên trái linh hoạt và trực quan thông qua nút bấm Python native.
- Bố cục bong bóng hội thoại trực quan (User bên phải, Assistant bên trái kèm avatar).
- Hàng nút tác vụ tiện ích: Xóa đoạn chat, Cuộc trò chuyện mới, Hoàn tác, Mở/Đóng Cài đặt.
- Loại bỏ hoàn toàn các thành phần thừa (watermark Gradio, các dropdown không cần thiết).
"""

PALETTE = {
    "primary": "#475569",         # Slate-600
    "primary_hover": "#334155",   # Slate-700
    "accent": "#2563EB",          # Blue-600
    "accent_hover": "#1D4ED8",    # Blue-700
    "bg_main": "#F8FAFC",         # Slate-50 nền dịu mắt
    "bg_card": "#FFFFFF",         # Card trắng sạch
    "border": "#E2E8F0",          # Slate-200 border
    "text_dark": "#0F172A",       # Slate-900 heading
    "text_body": "#334155",       # Slate-700 body
    "text_muted": "#64748B",      # Slate-500 subtext
}

CUSTOM_CSS = """
<style>
/* 1. Thiết lập chung & giới hạn độ rộng container */
.stApp {
    background-color: #F8FAFC !important;
    color: #0F172A !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
}

.block-container {
    max-width: 1280px !important;
    padding-top: 1.25rem !important;
    padding-bottom: 2rem !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    margin: 0 auto !important;
}

/* Ẩn các menu phụ và footer mặc định của Streamlit */
#MainMenu { visibility: hidden !important; display: none !important; }
footer { visibility: hidden !important; display: none !important; }
[data-testid="stToolbar"] { visibility: hidden !important; display: none !important; }
[data-testid="stDecoration"] { visibility: hidden !important; display: none !important; }
.viewerBadge_container__1QSob { display: none !important; }

/* 2. Header chính của Chatbox */
.chatbox-header-wrap {
    text-align: center;
    margin-bottom: 1.25rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid #E2E8F0;
}

.chatbox-header-title {
    font-size: 1.85rem !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    margin-bottom: 0.35rem !important;
    letter-spacing: -0.02em !important;
}

.chatbox-header-subtitle {
    font-size: 0.95rem !important;
    color: #64748B !important;
    margin-bottom: 0.6rem !important;
}

.chatbox-badges {
    display: inline-flex;
    gap: 8px;
    flex-wrap: wrap;
    justify-content: center;
}

.chatbox-badge-item {
    font-size: 0.8rem;
    font-weight: 500;
    padding: 3px 10px;
    border-radius: 9999px;
    background-color: #F1F5F9;
    color: #475569;
    border: 1px solid #E2E8F0;
}

.chatbox-badge-item.active {
    background-color: #ECFDF5;
    color: #059669;
    border-color: #A7F3D0;
}

/* 3. Bảng Cài Đặt Bên Trái (Settings Panel Card) */
.settings-panel-card {
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 16px !important;
    padding: 16px 18px !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05) !important;
    margin-bottom: 16px !important;
}

/* Card bao quanh khung chat chính (áp dụng cho container border=True) */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px !important;
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05) !important;
    margin-bottom: 12px !important;
}

/* 4. Bong bóng tin nhắn Người dùng (User) - NẰM BÊN PHẢI */
.user-msg-wrapper {
    display: flex !important;
    justify-content: flex-end !important;
    align-items: flex-start !important;
    width: 100% !important;
    margin-bottom: 16px !important;
}

.user-bubble-box {
    max-width: 78% !important;
    background-color: #3B82F6 !important;
    color: #FFFFFF !important;
    border-radius: 18px 18px 4px 18px !important;
    padding: 11px 18px !important;
    font-size: 0.96rem !important;
    line-height: 1.55 !important;
    box-shadow: 0 2px 4px rgba(59, 130, 246, 0.15) !important;
    margin-right: 10px !important;
    word-break: break-word !important;
}

.user-avatar-img {
    width: 36px !important;
    height: 36px !important;
    border-radius: 50% !important;
    border: 1px solid #CBD5E1 !important;
    flex-shrink: 0 !important;
}

/* 5. Bong bóng tin nhắn Chatbot (Assistant) - NẰM BÊN TRÁI */
.bot-msg-wrapper {
    display: flex !important;
    justify-content: flex-start !important;
    align-items: flex-start !important;
    width: 100% !important;
    margin-bottom: 18px !important;
}

.bot-avatar-img {
    width: 36px !important;
    height: 36px !important;
    border-radius: 50% !important;
    border: 1px solid #E2E8F0 !important;
    flex-shrink: 0 !important;
    margin-right: 10px !important;
}

.bot-bubble-box {
    max-width: 86% !important;
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 18px 18px 18px 4px !important;
    padding: 14px 20px !important;
    color: #0F172A !important;
    font-size: 0.96rem !important;
    line-height: 1.65 !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
    word-break: break-word !important;
}

/* 6. Hàng nhập liệu tin nhắn (Message Input Bar) */
div[data-testid="stForm"] {
    border: 1px solid #CBD5E1 !important;
    border-radius: 12px !important;
    padding: 6px 12px !important;
    background-color: #FFFFFF !important;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.03) !important;
    margin-top: 10px !important;
    margin-bottom: 10px !important;
}

div[data-testid="stForm"]:focus-within {
    border-color: #3B82F6 !important;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15) !important;
}

div[data-testid="stForm"] input {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    font-size: 0.96rem !important;
    color: #0F172A !important;
}

div[data-testid="stForm"] input:focus {
    outline: none !important;
    box-shadow: none !important;
}

div[data-testid="stForm"] div[data-testid="stButton"] button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    background-color: #3B82F6 !important;
    border: none !important;
    color: #FFFFFF !important;
    padding: 6px 16px !important;
    transition: background-color 0.15s ease !important;
}

div[data-testid="stForm"] div[data-testid="stButton"] button:hover {
    background-color: #2563EB !important;
}

/* 7. Hàng nút tác vụ (Clear, New, Undo, Settings) */
.chat-action-bar {
    margin-top: 8px !important;
}

.chat-action-bar div[data-testid="stButton"] button {
    background-color: #FFFFFF !important;
    color: #475569 !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: 0.88rem !important;
    height: 38px !important;
    transition: all 0.15s ease !important;
}

.chat-action-bar div[data-testid="stButton"] button:hover {
    background-color: #F1F5F9 !important;
    border-color: #94A3B8 !important;
    color: #0F172A !important;
}

/* Định dạng các thẻ markdown bên trong bot bubble */
.bot-bubble-box h1, .bot-bubble-box h2, .bot-bubble-box h3, .bot-bubble-box h4 {
    color: #0F172A !important;
    margin-top: 0.4rem !important;
    margin-bottom: 0.3rem !important;
}

.bot-bubble-box ul, .bot-bubble-box ol {
    margin-bottom: 0.4rem !important;
    padding-left: 1.25rem !important;
}

.bot-bubble-box code {
    background-color: #F1F5F9 !important;
    color: #0284C7 !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
    font-size: 0.9em !important;
}
</style>
"""
