"""Theme và CSS tùy biến cho giao diện Web Chatbox 2.0 (Streamlit).

Thiết kế chuẩn Web Desktop-style theo Visual Reference:
- Bố cục 2 phần: Sidebar bên trái (Logo, + Cuộc trò chuyện mới, Điều hướng 3 trang), Khung chính rộng rãi.
- Bảng màu Soft Slate (#475569, #0F172A, #FFFFFF, #F8FAFC, #E2E8F0).
- Ép Theme Sáng (Light Theme) đồng nhất bất kể hệ điều hành đang bật Dark mode.
- Khung hội thoại trung tâm cuộn tự nhiên theo viewport của trình duyệt, không tạo 2 thanh cuộn.
- Tin nhắn người dùng (BẠN) căn phải trong bong bóng xám nhạt (#F1F5F9).
- Tin nhắn chatbot đóng khung thẻ Card trắng có viền nhẹ (#E2E8F0) bằng container thật.
- Bảo toàn trọn vẹn Markdown, newline, từ loại, phiên âm và ví dụ câu.
- Thích ứng responsive trên cả màn hình desktop lẫn màn hình hẹp.
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
    "success": "#15803D",         # Green-700
    "success_bg": "#F0FDF4",      # Green-50
    "success_border": "#BBF7D0",  # Green-200
    "user_bubble_bg": "#F1F5F9",  # Slate-100 user bubble
}

# CSS tích hợp vào giao diện Streamlit
CUSTOM_CSS = """
<style>
/* ==========================================================================
   1. GHI ĐÈ BIẾN TOÀN CỤC & LIGHT THEME (KHÔNG DÙNG SELECTOR ÉP TOÀN BỘ CHỮ)
   ========================================================================== */
:root {
    --text-color: #0F172A !important;
    --background-color: #FFFFFF !important;
    --secondary-background-color: #F8FAFC !important;
    --primary-color: #475569 !important;
}

.stApp {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
}

/* Đặt màu văn bản chuẩn cho các khối nội dung chính, không đè lên các nhãn màu đặc biệt */
.stMarkdown p, .stMarkdown li, [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li {
    color: #0F172A;
}

.block-container {
    max-width: 980px !important;
    padding-top: 1.25rem !important;
    padding-bottom: 2rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    margin: 0 auto !important;
}

/* Ẩn thanh công cụ deploy và footer mặc định của Streamlit */
[data-testid="stToolbar"] {
    visibility: hidden !important;
    display: none !important;
}

footer {
    visibility: hidden !important;
    display: none !important;
}

header[data-testid="stHeader"], header[data-testid="stAppHeader"] {
    background-color: transparent !important;
}

/* Nút mở rộng Sidebar: Luôn hiển thị thanh lịch để không bao giờ bị mất thanh điều hướng */
[data-testid="stExpandSidebarButton"] {
    visibility: visible !important;
    display: flex !important;
    color: #0F172A !important;
    background-color: #FFFFFF !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
    padding: 6px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08) !important;
    z-index: 1000 !important;
    position: fixed !important;
    top: 14px !important;
    left: 14px !important;
    transition: all 0.15s ease-in-out !important;
}

[data-testid="stExpandSidebarButton"]:hover {
    background-color: #F1F5F9 !important;
    border-color: #94A3B8 !important;
}

[data-testid="stSidebarCollapseButton"] {
    visibility: visible !important;
    display: flex !important;
    color: #0F172A !important;
}

/* Ẩn iframe hỗ trợ ngầm của Streamlit components */
iframe[title*="streamlit_components"] {
    display: none !important;
    height: 0 !important;
    width: 0 !important;
    position: absolute !important;
}

/* ==========================================================================
   2. SIDEBAR BÊN TRÁI (LOGO, CUỘC TRÒ CHUYỆN MỚI, ĐIỀU HƯỚNG)
   ========================================================================== */
[data-testid="stSidebar"] {
    background-color: #FAFAFA !important;
    border-right: 1px solid #E2E8F0 !important;
}

[data-testid="stSidebarContent"] {
    padding: 1.25rem 1rem !important;
}

/* Logo & Tên ứng dụng ở Sidebar */
.sidebar-header-box {
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
    margin-bottom: 1.25rem !important;
    padding: 0 4px !important;
}

.sidebar-app-title {
    font-size: 1.22rem !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    letter-spacing: -0.01em !important;
}

.sidebar-app-icon {
    font-size: 1.4rem !important;
}

/* Nút Cuộc trò chuyện mới ở Sidebar */
[data-testid="stSidebar"] div[data-testid="stButton"] > button {
    width: 100% !important;
    border-radius: 8px !important;
    border: 1px solid #E2E8F0 !important;
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    font-weight: 500 !important;
    font-size: 0.92rem !important;
    padding: 9px 14px !important;
    text-align: center !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
    transition: all 0.15s ease-in-out !important;
}

[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
    background-color: #F1F5F9 !important;
    border-color: #CBD5E1 !important;
    color: #0F172A !important;
}

/* Đường phân cách Sidebar */
.sidebar-divider {
    height: 1px !important;
    background-color: #E2E8F0 !important;
    margin: 1.25rem 0 1rem 0 !important;
}

/* Tiêu đề mục ĐIỀU HƯỚNG */
.sidebar-section-title {
    font-size: 0.78rem !important;
    font-weight: 700 !important;
    color: #64748B !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    margin-bottom: 0.6rem !important;
    padding: 0 4px !important;
}

/* Ẩn nhãn tiêu đề mặc định của Streamlit st.radio */
[data-testid="stSidebar"] div[data-testid="stRadio"] > label {
    display: none !important;
}

/* Tinh chỉnh stRadioGroup thành Menu Danh sách hiện đại */
[data-testid="stRadioGroup"] {
    gap: 4px !important;
}

/* Ẩn hình tròn radio mặc định (độc lập với class sinh ngẫu nhiên) */
[data-testid="stRadioGroup"] label[data-testid="stRadioOption"] > div > div:first-child {
    display: none !important;
}

/* Tinh chỉnh từng item option của Radio */
[data-testid="stRadioGroup"] label[data-testid="stRadioOption"] {
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    padding: 9px 12px !important;
    border-radius: 8px !important;
    cursor: pointer !important;
    background-color: transparent !important;
    transition: all 0.15s ease !important;
    margin: 0 !important;
}

[data-testid="stRadioGroup"] label[data-testid="stRadioOption"]:hover {
    background-color: #F1F5F9 !important;
}

/* Item đang chọn (Active highlight) */
[data-testid="stRadioGroup"] div[data-selected="true"] label[data-testid="stRadioOption"],
[data-testid="stRadioGroup"] label[data-testid="stRadioOption"][data-selected="true"] {
    background-color: #F1F5F9 !important;
}

/* Màu chữ của item bình thường */
[data-testid="stRadioGroup"] label[data-testid="stRadioOption"] p {
    color: #475569 !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    margin: 0 !important;
    line-height: 1.4 !important;
}

/* Màu chữ của item đang chọn */
[data-testid="stRadioGroup"] div[data-selected="true"] label[data-testid="stRadioOption"] p,
[data-testid="stRadioGroup"] label[data-testid="stRadioOption"][data-selected="true"] p {
    color: #0F172A !important;
    font-weight: 700 !important;
}

/* Trạng thái Ollama ở chân Sidebar */
.sidebar-footer-status {
    display: flex !important;
    align-items: center !important;
    gap: 7px !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    margin-top: 2rem !important;
    padding: 0.75rem 0.5rem 0 0.5rem !important;
    border-top: 1px solid #E2E8F0 !important;
}

.sidebar-footer-status.online, .sidebar-footer-status.online * {
    color: #15803D !important;
}

.sidebar-footer-status.offline, .sidebar-footer-status.offline * {
    color: #DC2626 !important;
}

/* ==========================================================================
   3. KHUNG CHAT TRUNG TÂM (MAIN CHAT AREA)
   ========================================================================== */
.chat-top-bar {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    padding-bottom: 0.75rem !important;
    margin-bottom: 1.25rem !important;
    border-bottom: 1px solid #E2E8F0 !important;
}

.chat-top-left {
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
}

.chat-top-right {
    display: flex !important;
    align-items: center !important;
    gap: 12px !important;
    font-size: 0.85rem !important;
    color: #64748B !important;
}

.chat-view-title {
    font-size: 1.35rem !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    letter-spacing: -0.01em !important;
}

/* Badge Local màu xanh lá chuẩn */
.chat-local-pill {
    display: inline-flex !important;
    align-items: center !important;
    gap: 5px !important;
    background-color: #F0FDF4 !important;
    border: 1px solid #BBF7D0 !important;
    color: #15803D !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    padding: 2px 10px !important;
    border-radius: 9999px !important;
}

.chat-local-pill * {
    color: #15803D !important;
}

/* Trạng thái rỗng / Lời chào ban đầu (Empty State) */
.chat-empty-state-box {
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 5rem 1rem 3rem 1rem !important;
    text-align: center !important;
}

.chat-empty-icon {
    font-size: 2.6rem !important;
    color: #64748B !important;
    margin-bottom: 0.85rem !important;
}

.chat-empty-title {
    font-size: 1.3rem !important;
    font-weight: 600 !important;
    color: #0F172A !important;
    margin-bottom: 0.4rem !important;
}

.chat-empty-subtitle {
    font-size: 0.95rem !important;
    color: #64748B !important;
    max-width: 480px !important;
    line-height: 1.5 !important;
}

/* Tinh chỉnh st.chat_message chính thức */
[data-testid="stChatMessage"] {
    background-color: transparent !important;
    padding: 0 !important;
    margin-bottom: 1.25rem !important;
    gap: 0 !important;
}

/* Ẩn avatar ngoài mặc định của Streamlit vì đã có nhãn BẠN & thẻ Chatbox */
[data-testid="stChatMessage"] [data-testid="stChatMessageAvatar"] {
    display: none !important;
}

[data-testid="stChatMessage"] [data-testid="stChatMessageContent"] {
    width: 100% !important;
}

/* --------------------------------------------------------------------------
   3A. LƯỢT TIN NHẮN USER (BONG BÓNG XÁM CĂN PHẢI, NHÃN "BẠN")
   -------------------------------------------------------------------------- */
.user-turn-wrapper {
    display: flex !important;
    flex-direction: column !important;
    align-items: flex-end !important;
    width: 100% !important;
    margin-bottom: 0.5rem !important;
}

.user-turn-author {
    font-size: 0.75rem !important;
    font-weight: 700 !important;
    color: #64748B !important;
    letter-spacing: 0.05em !important;
    text-transform: uppercase !important;
    margin-bottom: 5px !important;
    text-align: right !important;
}

.user-turn-body {
    background-color: #F1F5F9 !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 16px 16px 4px 16px !important;
    padding: 10px 18px !important;
    color: #0F172A !important;
    font-size: 1rem !important;
    font-weight: 500 !important;
    line-height: 1.55 !important;
    word-break: break-word !important;
    white-space: pre-wrap !important;
    max-width: 100% !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
    text-align: left !important;
}

/* --------------------------------------------------------------------------
   3B. LƯỢT TIN NHẮN CHATBOT (CONTAINER THẬT ĐÓNG KHUNG THẺ CARD CÓ VIỀN NHẸ)
   -------------------------------------------------------------------------- */
/* Tác động trực tiếp vào container Streamlit thật của bot card */
[data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 12px !important;
    padding: 18px 22px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03) !important;
    margin-top: 4px !important;
    margin-bottom: 0.5rem !important;
    word-break: break-word !important;
}

.bot-card-header {
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    color: #0F172A !important;
    margin-bottom: 12px !important;
}

.bot-card-icon {
    font-size: 1.15rem !important;
}

.bot-card-title {
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    color: #0F172A !important;
}

/* Định dạng Markdown nội dung trả lời bên trong thẻ Card */
[data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] h1,
[data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] h2,
[data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] h3,
[data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] h4,
[data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] strong,
[data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] b {
    color: #0F172A !important;
    font-weight: 700 !important;
}

[data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] p {
    color: #0F172A !important;
    font-size: 1rem !important;
    line-height: 1.65 !important;
    margin-bottom: 0.6rem !important;
}

[data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] em,
[data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] i {
    color: #334155 !important;
    font-style: italic !important;
}

[data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] ol,
[data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] ul {
    margin-left: 1.25rem !important;
    margin-bottom: 0.6rem !important;
    color: #0F172A !important;
}

[data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] li {
    margin-bottom: 0.3rem !important;
    line-height: 1.55 !important;
    color: #0F172A !important;
}

/* Expander Nguồn dữ liệu & Inspector */
.stExpander, [data-testid="stExpander"] {
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
    background-color: #F8FAFC !important;
    margin-top: 10px !important;
}

[data-testid="stExpander"] summary, [data-testid="stExpander"] summary span, [data-testid="stExpander"] summary p {
    color: #334155 !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
}

.source-badge {
    display: inline-flex !important;
    align-items: center !important;
    gap: 4px !important;
    background-color: #FFFFFF !important;
    color: #334155 !important;
    font-size: 0.82rem !important;
    padding: 4px 10px !important;
    border-radius: 6px !important;
    border: 1px solid #E2E8F0 !important;
    margin-right: 6px !important;
    margin-top: 4px !important;
}

.source-badge b, .source-badge strong {
    color: #0F172A !important;
}

/* ==========================================================================
   4. Ô NHẬP LIỆU & THANH CHÂN TRANG (BOTTOM CONTAINER)
   ========================================================================== */
/* Bắt buộc màu nền trắng cho toàn bộ thanh dưới đáy, xóa nền đen */
[data-testid="stBottom"], [data-testid="stBottom"] > div, .stBottom, section[data-testid="stBottom"] {
    background-color: #FFFFFF !important;
    background: #FFFFFF !important;
    border-top: 1px solid #F1F5F9 !important;
}

[data-testid="stChatInput"] {
    max-width: 980px !important;
    background-color: transparent !important;
    background: transparent !important;
}

[data-testid="stChatInput"] > div {
    background-color: #FFFFFF !important;
    background: #FFFFFF !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
}

[data-testid="stChatInput"] textarea {
    background-color: transparent !important;
    color: #0F172A !important;
    font-size: 0.95rem !important;
}

[data-testid="stChatInput"] textarea::placeholder {
    color: #94A3B8 !important;
}

[data-testid="stChatInput"] textarea:focus {
    box-shadow: none !important;
}

/* Nút Gửi mũi tên */
[data-testid="stChatInputSubmitButton"] {
    color: #0F172A !important;
}

/* Dòng trạng thái chân khung chat */
.chat-bottom-status-line {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    font-size: 0.82rem !important;
    color: #64748B !important;
    margin-top: 1.5rem !important;
    margin-bottom: 0.5rem !important;
    padding: 0 4px !important;
}

.status-dot {
    display: inline-flex !important;
    align-items: center !important;
    gap: 5px !important;
    font-weight: 500 !important;
}

.status-dot.online, .status-dot.online * {
    color: #15803D !important;
}

.status-dot.offline, .status-dot.offline * {
    color: #DC2626 !important;
}

/* ==========================================================================
   5. CÁC PANEL QUẢN LÝ DỮ LIỆU & CHẨN ĐOÁN
   ========================================================================== */
/* Áp dụng giao diện thẻ phẳng thanh lịch cho các container có viền */
.main [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02) !important;
}

.panel-card-header {
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
    font-size: 1.15rem !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    margin-bottom: 12px !important;
}

.metric-box {
    background-color: #F8FAFC !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 10px !important;
    padding: 14px 16px !important;
    margin-bottom: 12px !important;
}

.metric-label {
    font-size: 0.8rem !important;
    color: #64748B !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    margin-bottom: 4px !important;
}

.metric-value {
    font-size: 1.25rem !important;
    font-weight: 700 !important;
    color: #0F172A !important;
}

.metric-caption {
    font-size: 0.78rem !important;
    color: #64748B !important;
    margin-top: 3px !important;
}

/* ==========================================================================
   6. TỐI ƯU RESPONSIVE MÀN HÌNH NHỎ (< 768px)
   ========================================================================== */
@media (max-width: 768px) {
    .block-container {
        padding-left: 0.85rem !important;
        padding-right: 0.85rem !important;
        padding-top: 0.85rem !important;
    }
    
    .chat-view-title {
        font-size: 1.15rem !important;
    }
    
    .chat-empty-state-box {
        padding: 3rem 0.5rem 1.5rem 0.5rem !important;
    }

    .user-turn-body {
        max-width: 95% !important;
    }
}
</style>
"""
