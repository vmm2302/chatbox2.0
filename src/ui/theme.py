"""Theme và CSS tùy biến cho giao diện Chatbox 2.0 (Streamlit).

Thiết kế tối giản, tập trung vào trải nghiệm tra cứu từ vựng:
- Bố cục 1 cột trung tâm (max-width: 900px) căn giữa màn hình, co giãn responsive.
- Bảng màu Soft Slate (#475569, #0F172A, #F8FAFC, #E2E8F0).
- Khung chat tinh gọn: Tin nhắn User (bên phải), Chatbot (bên trái).
- Định dạng Markdown chuẩn bảo toàn cấu trúc từ loại, phiên âm, ví dụ.
- Thẻ nguồn dữ liệu và metric lưu trữ tối giản, chuyên nghiệp.
"""

# Bảng màu chuẩn Soft Slate
PALETTE = {
    "primary": "#475569",         # Slate-600
    "primary_hover": "#334155",   # Slate-700
    "accent": "#2563EB",          # Blue-600
    "bg_main": "#FFFFFF",         # Nền sáng
    "bg_card": "#F8FAFC",         # Slate-50 card background
    "border": "#E2E8F0",          # Slate-200 border
    "text_dark": "#0F172A",       # Slate-900 heading
    "text_body": "#334155",       # Slate-700 body
    "text_muted": "#64748B",      # Slate-500 subtext
}

# CSS tích hợp vào giao diện Streamlit
CUSTOM_CSS = """
<style>
/* 1. Thiết lập chung & giới hạn độ rộng container 1 cột trung tâm */
.stApp {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
}

.block-container {
    max-width: 920px !important;
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
    padding-left: 1.25rem !important;
    padding-right: 1.25rem !important;
    margin: 0 auto !important;
}

/* Ẩn header và footer mặc định của Streamlit */
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}

/* 2. Tiêu đề ứng dụng & Thanh trạng thái */
.app-header-container {
    margin-bottom: 1.25rem !important;
    padding-bottom: 0.75rem !important;
    border-bottom: 1px solid #E2E8F0 !important;
}

.app-title {
    font-size: 1.65rem !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    margin-bottom: 0.35rem !important;
    letter-spacing: -0.02em !important;
}

.app-subtitle {
    font-size: 0.92rem !important;
    color: #64748B !important;
    margin-bottom: 0.75rem !important;
}

.header-badges {
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
    flex-wrap: wrap !important;
}

.status-badge {
    display: inline-flex !important;
    align-items: center !important;
    gap: 6px !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    padding: 3px 10px !important;
    border-radius: 9999px !important;
    border: 1px solid #E2E8F0 !important;
    background-color: #F8FAFC !important;
    color: #334155 !important;
}

.status-badge.online {
    background-color: #F0FDF4 !important;
    border-color: #BBF7D0 !important;
    color: #166534 !important;
}

.status-badge.offline {
    background-color: #FEF2F2 !important;
    border-color: #FECACA !important;
    color: #991B1B !important;
}

/* 3. Tinh chỉnh Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 16px !important;
    background-color: transparent !important;
    border-bottom: 2px solid #F1F5F9 !important;
    padding-bottom: 0 !important;
    margin-bottom: 1.25rem !important;
}

.stTabs [data-baseweb="tab"] {
    border: none !important;
    background: transparent !important;
    padding: 10px 14px 12px 14px !important;
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

/* 4. Khung Card Panel */
.panel-card {
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 12px !important;
    padding: 18px 20px !important;
    margin-bottom: 16px !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02) !important;
}

.panel-card-header {
    display: inline-flex !important;
    align-items: center !important;
    gap: 6px !important;
    font-size: 0.9rem !important;
    font-weight: 600 !important;
    color: #334155 !important;
    background-color: #F1F5F9 !important;
    padding: 4px 10px !important;
    border-radius: 8px !important;
    border: 1px solid #E2E8F0 !important;
    margin-bottom: 12px !important;
}

/* 5. Thẻ chào mừng trạng thái rỗng */
.welcome-card {
    background-color: #F8FAFC !important;
    border: 1px dashed #CBD5E1 !important;
    border-radius: 14px !important;
    padding: 28px 24px !important;
    text-align: center !important;
    margin: 20px 0 24px 0 !important;
}

.welcome-title {
    font-size: 1.15rem !important;
    font-weight: 600 !important;
    color: #0F172A !important;
    margin-bottom: 8px !important;
}

.welcome-text {
    font-size: 0.92rem !important;
    color: #475569 !important;
    line-height: 1.6 !important;
    max-width: 640px !important;
    margin: 0 auto !important;
}

/* 6. Nút bấm tinh tế */
div[data-testid="stButton"] > button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: 0.88rem !important;
    border: 1px solid #CBD5E1 !important;
    background-color: #FFFFFF !important;
    color: #334155 !important;
    padding: 6px 14px !important;
    transition: all 0.15s ease-in-out !important;
}

div[data-testid="stButton"] > button:hover {
    background-color: #F8FAFC !important;
    border-color: #94A3B8 !important;
    color: #0F172A !important;
}

div[data-testid="stButton"] > button[kind="primary"] {
    background-color: #0F172A !important;
    border-color: #0F172A !important;
    color: #FFFFFF !important;
}

div[data-testid="stButton"] > button[kind="primary"]:hover {
    background-color: #334155 !important;
    border-color: #334155 !important;
}

/* Nút Cuộc trò chuyện mới */
.btn-new-chat-container {
    display: flex !important;
    justify-content: flex-end !important;
    margin-bottom: 10px !important;
}

/* 7. Bong bóng chat */
.user-msg-wrapper {
    display: flex !important;
    justify-content: flex-end !important;
    align-items: flex-start !important;
    width: 100% !important;
    margin-bottom: 14px !important;
}

.user-bubble-box {
    max-width: 78% !important;
    background-color: #F1F5F9 !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 16px 16px 4px 16px !important;
    padding: 10px 16px !important;
    color: #0F172A !important;
    font-size: 0.95rem !important;
    line-height: 1.5 !important;
    margin-right: 10px !important;
    word-break: break-word !important;
}

.user-avatar-img {
    width: 32px !important;
    height: 32px !important;
    border-radius: 50% !important;
    border: 1px solid #CBD5E1 !important;
    flex-shrink: 0 !important;
}

.bot-msg-wrapper {
    display: flex !important;
    justify-content: flex-start !important;
    align-items: flex-start !important;
    width: 100% !important;
    margin-bottom: 14px !important;
}

.bot-avatar-img {
    width: 32px !important;
    height: 32px !important;
    border-radius: 50% !important;
    border: 1px solid #E2E8F0 !important;
    flex-shrink: 0 !important;
    margin-right: 10px !important;
}

.bot-bubble-box {
    max-width: 86% !important;
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 16px 16px 16px 4px !important;
    padding: 14px 18px !important;
    color: #0F172A !important;
    font-size: 0.95rem !important;
    line-height: 1.6 !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02) !important;
    word-break: break-word !important;
}

/* 8. Nguồn dữ liệu badge */
.source-badge {
    display: inline-flex !important;
    align-items: center !important;
    gap: 4px !important;
    background-color: #F1F5F9 !important;
    color: #475569 !important;
    font-size: 0.78rem !important;
    padding: 2px 8px !important;
    border-radius: 6px !important;
    border: 1px solid #E2E8F0 !important;
    margin-right: 6px !important;
    margin-top: 4px !important;
}

/* 9. Metric card đơn giản cho Tab Quản Lý & Chẩn Đoán */
.metric-box {
    background-color: #F8FAFC !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 10px !important;
    padding: 12px 16px !important;
    margin-bottom: 10px !important;
}

.metric-label {
    font-size: 0.8rem !important;
    color: #64748B !important;
    font-weight: 500 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.03em !important;
    margin-bottom: 4px !important;
}

.metric-value {
    font-size: 1.15rem !important;
    font-weight: 700 !important;
    color: #0F172A !important;
}

.metric-caption {
    font-size: 0.76rem !important;
    color: #64748B !important;
    margin-top: 2px !important;
}

/* 10. Tối ưu Responsive trên màn hình di động */
@media (max-width: 768px) {
    .block-container {
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
        padding-top: 1rem !important;
    }
    
    .user-bubble-box {
        max-width: 88% !important;
    }
    
    .bot-bubble-box {
        max-width: 92% !important;
        padding: 12px 14px !important;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 8px 10px !important;
        font-size: 0.88rem !important;
    }
}
</style>
"""
