"""Theme và CSS tùy biến cho giao diện Chatbox 2.0 (Streamlit).

Được đồng bộ 100% phong cách thiết kế từ Gradio (rag-chatbot-main / demo.png):
- Khung container 1280px bo góc mềm mại, bảng màu Soft Slate (#64748B, #FF7373).
- 2 Panel card độc lập viền #E2E8F0: Cột trái (Setting Panel) và Cột phải (Chatbot Viewport).
- Hộp Status dạng ô Textbox chuẩn Gradio (Ready!, Answering!, Completed!).
- Radio chọn Language dạng nút bấm phân đoạn (segmented pills: vi / eng).
- Khung chat với tin nhắn Người Dùng ở BÊN PHẢI và tin nhắn Chatbot ở BÊN TRÁI.
- Hàng nhập inline [QA ▾] [Enter you message:] [➤] nằm trọn trong card chat.
- Hàng 4 nút tác vụ bên dưới: [Hide Setting] [Undo] [Clear] [Reset].
- Chân trang: Built with Gradio 🧡.
"""

# Bảng màu chuẩn từ rag-chatbot-main (theme.py & demo.png)
PALETTE = {
    "primary": "#64748B",         # Slate-500 (.btn background)
    "primary_hover": "#475569",   # Slate-600
    "stop": "#FF7373",            # Stop / Reset button (.stop_btn)
    "stop_hover": "#E05252",
    "bg_main": "#FFFFFF",         # Nền sáng sạch
    "bg_card": "#FFFFFF",         # Card panel background
    "border": "#E2E8F0",          # Slate-200 border
    "text_dark": "#0F172A",       # Slate-900 heading
    "text_body": "#334155",       # Slate-700 body
    "text_muted": "#64748B",      # Slate-500 subtext
}

# CSS tích hợp sâu vào giao diện Streamlit
CUSTOM_CSS = """
<style>
/* 1. Thiết lập chung & giới hạn độ rộng container 1280px chuẩn demo.png */
.stApp {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
}

.block-container {
    max-width: 1280px !important;
    padding-top: 1.25rem !important;
    padding-bottom: 2rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    margin: 0 auto !important;
}

/* Ẩn header và footer mặc định của Streamlit */
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}

/* 2. Tiêu đề ứng dụng chuẩn demo.png */
.gr-app-title {
    font-size: 1.85rem !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    margin-top: 0 !important;
    margin-bottom: 0.75rem !important;
    letter-spacing: -0.02em !important;
}

/* 3. Tinh chỉnh Tabs chuẩn Soft Slate từ Gradio */
.stTabs [data-baseweb="tab-list"] {
    gap: 20px !important;
    background-color: transparent !important;
    border-bottom: 1px solid #E2E8F0 !important;
    padding-bottom: 0 !important;
    margin-bottom: 1.2rem !important;
}

.stTabs [data-baseweb="tab"] {
    border: none !important;
    background: transparent !important;
    padding: 8px 12px 10px 12px !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    color: #64748B !important;
    border-bottom: 2px solid transparent !important;
    transition: all 0.15s ease !important;
}

.stTabs [data-baseweb="tab"]:hover {
    color: #0F172A !important;
}

.stTabs [aria-selected="true"] {
    color: #0F172A !important;
    font-weight: 600 !important;
    background: transparent !important;
    border-bottom: 2px solid #0F172A !important;
}

.stTabs [data-baseweb="tab-highlight"] {
    background-color: #0F172A !important;
}

/* 4. Khung Card Panel viền xám nhạt bo tròn 12px chuẩn demo.png */
.panel-card {
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 12px !important;
    padding: 16px 18px !important;
    margin-bottom: 16px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02) !important;
}

.panel-card-header {
    display: inline-flex !important;
    align-items: center !important;
    gap: 6px !important;
    font-size: 0.88rem !important;
    font-weight: 600 !important;
    color: #334155 !important;
    background-color: #F1F5F9 !important;
    padding: 4px 10px !important;
    border-radius: 8px !important;
    border: 1px solid #E2E8F0 !important;
    margin-bottom: 12px !important;
}

/* 5. Khung Status Box chuẩn ô Textbox Gradio */
.gr-label {
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    color: #475569 !important;
    margin-bottom: 5px !important;
}

.gr-status-textbox {
    background-color: #F8FAFC !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
    padding: 9px 12px !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    color: #0F172A !important;
    margin-bottom: 14px !important;
    display: flex !important;
    align-items: center !important;
    min-height: 38px !important;
}

/* 6. Radio chọn Language dạng Segmented Pills chuẩn demo.png */
div[data-testid="stRadio"] > div {
    display: flex !important;
    flex-direction: row !important;
    gap: 8px !important;
}

div[data-testid="stRadio"] label {
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
    padding: 4px 18px !important;
    background: #FFFFFF !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
}

div[data-testid="stRadio"] label:has(input:checked) {
    background-color: #475569 !important;
    border-color: #475569 !important;
}

div[data-testid="stRadio"] label:has(input:checked) p {
    color: #FFFFFF !important;
    font-weight: 600 !important;
}

/* 7. Nút bấm Upload và Reset chuẩn .btn và .stop_btn */
div[data-testid="stButton"] > button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: 0.9rem !important;
    border: 1px solid #CBD5E1 !important;
    background-color: #FFFFFF !important;
    color: #334155 !important;
    padding: 6px 16px !important;
    transition: all 0.15s ease-in-out !important;
}

div[data-testid="stButton"] > button:hover {
    background-color: #F8FAFC !important;
    border-color: #94A3B8 !important;
    color: #0F172A !important;
}

/* Nút Primary kiểu .btn (#64748B) */
div[data-testid="stButton"] > button[kind="primary"] {
    background-color: #64748B !important;
    border-color: #475569 !important;
    color: #FFFFFF !important;
}

div[data-testid="stButton"] > button[kind="primary"]:hover {
    background-color: #475569 !important;
    border-color: #334155 !important;
}

/* 8. Hàng 4 nút tác vụ (Hide Setting, Undo, Clear, Reset) chuẩn demo.png */
.chat-action-bar {
    margin-top: 10px !important;
    padding-top: 4px !important;
}

.chat-action-bar div[data-testid="stButton"] button {
    background-color: #FFFFFF !important;
    color: #334155 !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: 0.9rem !important;
    height: 38px !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02) !important;
}

.chat-action-bar div[data-testid="stButton"] button:hover {
    background-color: #F8FAFC !important;
    border-color: #CBD5E1 !important;
    color: #0F172A !important;
}

/* 9. Bố cục tin nhắn: Người dùng BÊN PHẢI, Chatbot BÊN TRÁI */
/* Tin nhắn Người Dùng (User) - BÊN PHẢI */
.user-msg-wrapper {
    display: flex !important;
    justify-content: flex-end !important;
    align-items: flex-start !important;
    width: 100% !important;
    margin-bottom: 14px !important;
}

.user-bubble-box {
    max-width: 75% !important;
    background-color: #F1F5F9 !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 18px 18px 4px 18px !important;
    padding: 10px 16px !important;
    color: #0F172A !important;
    font-size: 0.95rem !important;
    line-height: 1.5 !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
    margin-right: 10px !important;
    word-break: break-word !important;
}

.user-avatar-img {
    width: 35px !important;
    height: 35px !important;
    border-radius: 50% !important;
    border: 1px solid #CBD5E1 !important;
    flex-shrink: 0 !important;
}

/* Tin nhắn Chatbot (Assistant) - BÊN TRÁI */
.bot-msg-wrapper {
    display: flex !important;
    justify-content: flex-start !important;
    align-items: flex-start !important;
    width: 100% !important;
    margin-bottom: 14px !important;
}

.bot-avatar-img {
    width: 35px !important;
    height: 35px !important;
    border-radius: 50% !important;
    border: 1px solid #E2E8F0 !important;
    flex-shrink: 0 !important;
    margin-right: 10px !important;
}

.bot-bubble-box {
    max-width: 82% !important;
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 18px 18px 18px 4px !important;
    padding: 14px 20px !important;
    color: #0F172A !important;
    font-size: 0.95rem !important;
    line-height: 1.6 !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02) !important;
    word-break: break-word !important;
}

/* Áp dụng thêm CSS cho stChatMessage nếu có */
.user-msg-wrapper div[data-testid="stChatMessage"],
div[data-testid="stChatMessage"]:has(img[src*="user"]) {
    flex-direction: row-reverse !important;
    margin-left: auto !important;
    margin-right: 0 !important;
    max-width: 78% !important;
    background-color: #F1F5F9 !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 18px 18px 4px 18px !important;
    padding: 8px 14px !important;
}

.user-msg-wrapper div[data-testid="stChatMessageContent"],
div[data-testid="stChatMessage"]:has(img[src*="user"]) div[data-testid="stChatMessageContent"] {
    text-align: left !important;
    margin-right: 10px !important;
    margin-left: 0 !important;
}

.bot-msg-wrapper div[data-testid="stChatMessage"],
div[data-testid="stChatMessage"]:has(img[src*="bot"]) {
    flex-direction: row !important;
    margin-left: 0 !important;
    margin-right: auto !important;
    max-width: 85% !important;
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 18px 18px 18px 4px !important;
    padding: 12px 18px !important;
}

.bot-msg-wrapper div[data-testid="stChatMessageContent"],
div[data-testid="stChatMessage"]:has(img[src*="bot"]) div[data-testid="stChatMessageContent"] {
    text-align: left !important;
    margin-left: 10px !important;
    margin-right: 0 !important;
}

/* 10. Hàng nhập liệu inline dạng card mềm liền khối chuẩn demo.png */
div[data-testid="stForm"] {
    border: 1px solid #E2E8F0 !important;
    border-radius: 10px !important;
    padding: 4px 8px !important;
    background-color: #FFFFFF !important;
    margin-top: 8px !important;
    margin-bottom: 8px !important;
}

div[data-testid="stForm"] div[data-testid="stSelectbox"] div[data-baseweb="select"] {
    border: none !important;
    background: transparent !important;
}

div[data-testid="stForm"] input {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
}

div[data-testid="stForm"] div[data-testid="stButton"] button {
    border: none !important;
    background: transparent !important;
    color: #64748B !important;
    font-size: 1.15rem !important;
    padding: 0 4px !important;
}

div[data-testid="stForm"] div[data-testid="stButton"] button:hover {
    color: #0F172A !important;
}
</style>
"""
