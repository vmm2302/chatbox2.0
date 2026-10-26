"""Theme và CSS tùy biến cho giao diện Web Chatbox 2.0 (Streamlit).

Thiết kế chuẩn Web Desktop-style theo Visual Reference:
- Bố cục 2 phần: Sidebar bên trái (Logo, + Cuộc trò chuyện mới, Điều hướng 3 trang), Khung chính rộng rãi.
- Bảng màu Soft Slate (#475569, #0F172A, #FFFFFF, #F8FAFC, #E2E8F0).
- Ép Theme Sáng (Light Theme) đồng nhất bất kể hệ điều hành đang bật Dark mode.
- Khung hội thoại trung tâm cuộn tự nhiên theo viewport của trình duyệt, không tạo 2 thanh cuộn.
- Tin nhắn người dùng căn phải với icon trong bong bóng xám nhạt (#F1F5F9).
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
    overflow-x: hidden !important;
}

/* Đặt màu văn bản chuẩn cho các khối nội dung chính, không đè lên các nhãn màu đặc biệt */
.stMarkdown p, .stMarkdown li, [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li {
    color: #0F172A;
}

.block-container {
    max-width: 980px !important;
    width: 100% !important;
    padding-top: 1.25rem !important;
    padding-bottom: 7rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    margin: 0 auto !important;
    box-sizing: border-box !important;
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

/* ==========================================================================
   2. KHÓA BỐ CỤC SIDEBAR & VÔ HIỆU HÓA HOÀN TOÀN THANH KÉO RESIZE
   ========================================================================== */
/* Vô hiệu hóa tay nắm kéo thay đổi kích thước sidebar */
[data-testid="stSidebar"] .react-resizable-handle,
[data-testid="stSidebarResizeHandle"] {
    display: none !important;
    pointer-events: none !important;
}

/* Khóa chiều rộng sidebar ở 260px khi đang mở */
section[data-testid="stSidebar"][aria-expanded="true"] {
    width: 260px !important;
    min-width: 260px !important;
    max-width: 260px !important;
    flex: 0 0 260px !important;
}

/* Vô hiệu hóa triệt để thanh kéo resize handle của Streamlit trên mọi kích thước màn hình */
[data-testid="stSidebar"] [data-testid="stSidebarResizeHandle"],
div[data-testid="stSidebarResizeHandle"],
.stSidebar > div[data-testid="stSidebarResizeHandle"],
.stSidebar > div[style*="col-resize"],
.stSidebar > div:last-child[style*="cursor"] {
    display: none !important;
    visibility: hidden !important;
    pointer-events: none !important;
    cursor: default !important;
    width: 0 !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
    background: transparent !important;
    opacity: 0 !important;
    user-select: none !important;
}

/* Vô hiệu hóa con trỏ kéo dãn trên ranh giới sidebar */
[data-testid="stSidebar"], .stSidebar {
    cursor: default !important;
    background-color: #FAFAFA !important;
    border-right: 1px solid #E2E8F0 !important;
}

@media (min-width: 769px) {
    /* Khóa sidebar luôn mở trên Desktop: Ẩn nút đóng và nút mở rộng */
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stExpandSidebarButton"],
    [data-testid="stSidebarCollapsedControl"],
    header[data-testid="stHeader"] [data-testid="stSidebarCollapsedControl"] {
        display: none !important;
        visibility: hidden !important;
        pointer-events: none !important;
    }

    /* Thu gọn header rỗng của sidebar trên desktop vì không còn nút đóng */
    [data-testid="stSidebarHeader"] {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        height: 0 !important;
        min-height: 0 !important;
        visibility: hidden !important;
    }

    /* Khóa chiều rộng sidebar cố định đúng 260px trên Desktop, không cho phép co giãn */
    section[data-testid="stSidebar"],
    .stSidebar,
    [data-testid="stSidebar"] {
        width: 260px !important;
        min-width: 260px !important;
        max-width: 260px !important;
        flex: 0 0 260px !important;
        flex-basis: 260px !important;
        flex-grow: 0 !important;
        flex-shrink: 0 !important;
        transform: none !important;
        transition: none !important;
        overflow-x: hidden !important;
    }

    [data-testid="stSidebarContent"] {
        width: 260px !important;
        min-width: 260px !important;
        max-width: 260px !important;
        overflow-x: hidden !important;
        padding: 1.25rem 1rem !important;
    }

    /* Khóa khung hội thoại chính bên phải: Chiếm trọn phần không gian còn lại (100% - 260px) */
    section[data-testid="stMain"],
    .stMain,
    [data-testid="stMain"] {
        flex: 1 1 0% !important;
        min-width: 0 !important;
        overflow-x: hidden !important;
    }
}

@media (max-width: 768px) {
    /* Trên màn hình nhỏ: Cho phép nút hamburger / đóng mở hiển thị bình thường */
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stExpandSidebarButton"],
    [data-testid="stSidebarCollapsedControl"] {
        display: flex !important;
        visibility: visible !important;
    }

    section[data-testid="stSidebar"],
    .stSidebar,
    [data-testid="stSidebar"] {
        max-width: 85vw !important;
    }
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

[data-testid="stSidebar"] div[data-testid="stButton"] > button * {
    color: #0F172A !important;
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

/* Tinh chỉnh stRadioGroup thành Menu Danh sách hiện đại chỉ riêng trong Sidebar */
[data-testid="stSidebar"] [data-testid="stRadioGroup"] {
    gap: 4px !important;
}

/* Ẩn hình tròn radio mặc định (chỉ trong Sidebar) */
[data-testid="stSidebar"] [data-testid="stRadioGroup"] label[data-testid="stRadioOption"] > div > div:first-child {
    display: none !important;
}

/* Tinh chỉnh từng item option của Radio trong Sidebar */
[data-testid="stSidebar"] [data-testid="stRadioGroup"] label[data-testid="stRadioOption"] {
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

[data-testid="stSidebar"] [data-testid="stRadioGroup"] label[data-testid="stRadioOption"]:hover {
    background-color: #F1F5F9 !important;
}

/* Item đang chọn (Active highlight) trong Sidebar */
[data-testid="stSidebar"] [data-testid="stRadioGroup"] div[data-selected="true"] label[data-testid="stRadioOption"],
[data-testid="stSidebar"] [data-testid="stRadioGroup"] label[data-testid="stRadioOption"][data-selected="true"] {
    background-color: #F1F5F9 !important;
}

/* Màu chữ của item bình thường trong Sidebar */
[data-testid="stSidebar"] [data-testid="stRadioGroup"] label[data-testid="stRadioOption"] p {
    color: #475569 !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    margin: 0 !important;
    line-height: 1.4 !important;
}

/* Màu chữ của item đang chọn trong Sidebar */
[data-testid="stSidebar"] [data-testid="stRadioGroup"] div[data-selected="true"] label[data-testid="stRadioOption"] p,
[data-testid="stSidebar"] [data-testid="stRadioGroup"] label[data-testid="stRadioOption"][data-selected="true"] p {
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

/* Ẩn hoàn toàn icon người dùng bên trái mặc định của Streamlit (tránh trùng lặp với icon bên phải) */
[data-testid="stChatMessage"]:has(.user-turn-wrapper) > div:first-child:not([data-testid="stChatMessageContent"]),
[data-testid="stChatMessage"]:has(.user-turn-wrapper) > img:first-child,
[data-testid="stChatMessage"]:has(.user-turn-wrapper) [data-testid*="ChatMessageAvatar"],
[data-testid="stChatMessage"]:has(.user-turn-wrapper) img[alt*="avatar"],
[data-testid="stChatMessage"] img[alt="user avatar"],
[data-testid="stChatMessage"] [data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessage"]:has(.user-turn-wrapper) [data-testid="stChatMessageAvatar"] {
    display: none !important;
    visibility: hidden !important;
    width: 0 !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
}

[data-testid="stChatMessage"]:has(.user-turn-wrapper) {
    gap: 0 !important;
}

[data-testid="stChatMessage"] [data-testid="stChatMessageContent"] {
    width: 100% !important;
    padding: 0 !important;
    overflow: visible !important;
}

/* --------------------------------------------------------------------------
   3A. LƯỢT TIN NHẮN USER (BONG BÓNG XÁM CĂN PHẢI, ICON NGƯỜI DÙNG CÓ SẴN)
   -------------------------------------------------------------------------- */
.user-turn-wrapper {
    display: flex !important;
    flex-direction: column !important;
    align-items: flex-end !important;
    width: 100% !important;
    margin-bottom: 0.5rem !important;
}

.user-turn-author {
    display: flex !important;
    align-items: center !important;
    justify-content: flex-end !important;
    margin-bottom: 5px !important;
    padding-right: 4px !important;
    min-height: 32px !important;
}

.user-turn-avatar,
.user-turn-author img,
[data-testid="stChatMessage"] .user-turn-author img,
[data-testid="stMarkdownContainer"] img.user-turn-avatar {
    width: 32px !important;
    height: 32px !important;
    max-width: 32px !important;
    max-height: 32px !important;
    object-fit: contain !important;
    display: inline-block !important;
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
    overflow-wrap: break-word !important;
    white-space: pre-wrap !important;
    width: fit-content !important;
    max-width: 100% !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
    text-align: left !important;
}

/* --------------------------------------------------------------------------
   3B. LƯỢT TIN NHẮN CHATBOT (CONTAINER THẬT ĐÓNG KHUNG THẺ CARD CÓ VIỀN NHẸ)
   -------------------------------------------------------------------------- */
/* Tác động trực tiếp vào container Streamlit thật của bot card */
[data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] {
    display: block !important;
    width: fit-content !important;
    min-width: 220px !important;
    max-width: 100% !important;
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 12px !important;
    padding: 18px 22px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03) !important;
    margin-top: 4px !important;
    margin-bottom: 0.5rem !important;
    word-break: break-word !important;
    overflow-wrap: break-word !important;
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

/* Chỉ báo trạng thái đang xử lý bên trong thẻ bot */
.bot-status-indicator {
    color: #64748B !important;
    font-size: 0.92rem !important;
    display: inline-flex !important;
    align-items: center !important;
    gap: 8px !important;
    margin: 4px 0 10px 0 !important;
    font-style: italic !important;
    line-height: 1.4 !important;
}

.bot-status-indicator .status-spinner {
    font-size: 1rem !important;
    font-style: normal !important;
    display: inline-block !important;
    animation: status-pulse 1.5s infinite ease-in-out !important;
}

@keyframes status-pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.4; transform: scale(0.95); }
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
    width: 100% !important;
    margin: 0 auto !important;
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
   5. CÁC PANEL QUẢN LÝ DỮ LIỆU & CHẨN ĐOÁN (LIGHT THEME ĐỒNG BỘ)
   ========================================================================== */
/* Áp dụng giao diện thẻ phẳng thanh lịch cho các container có viền */
[data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"],
.main [data-testid="stVerticalBlockBorderWrapper"] {
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

/* Thẻ chỉ số & Thống kê (Stat Cards) */
.stat-card-label {
    font-size: 0.78rem !important;
    color: #64748B !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    margin-bottom: 4px !important;
}

.stat-card-value {
    font-size: 1.25rem !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    line-height: 1.3 !important;
    word-break: break-word !important;
}

.stat-card-caption {
    font-size: 0.78rem !important;
    color: #64748B !important;
    margin-top: 3px !important;
    word-break: break-all !important;
}

.stat-card-error {
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    color: #DC2626 !important;
    margin-top: 3px !important;
}

/* Lớp tương thích ngược cho Metric-box */
.metric-box {
    background-color: #F8FAFC !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 10px !important;
    padding: 12px 14px !important;
    margin-bottom: 8px !important;
}

.metric-label {
    font-size: 0.78rem !important;
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

/* Radio Group trong Khung chính (Ví dụ: Chế độ ADD/REPLACE) */
[data-testid="stMain"] [data-testid="stRadioGroup"] {
    gap: 8px !important;
}

[data-testid="stMain"] [data-testid="stRadioGroup"] label[data-testid="stRadioOption"] {
    display: flex !important;
    align-items: center !important;
    cursor: pointer !important;
    padding: 6px 10px !important;
    border-radius: 8px !important;
    transition: background-color 0.15s ease !important;
}

[data-testid="stMain"] [data-testid="stRadioGroup"] label[data-testid="stRadioOption"]:hover {
    background-color: #F8FAFC !important;
}

[data-testid="stMain"] [data-testid="stRadioGroup"] label[data-testid="stRadioOption"] p {
    color: #0F172A !important;
    font-size: 0.95rem !important;
    margin: 0 !important;
}

[data-testid="stMain"] [data-testid="stRadio"] label {
    color: #334155 !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
}

/* Checkbox (st.checkbox) - Đảm bảo ô chọn có nền sáng, viền rõ nét, không bị đen */
[data-testid="stCheckbox"] {
    margin: 0.5rem 0 !important;
}

[data-testid="stCheckbox"] label {
    color: #0F172A !important;
    font-size: 0.92rem !important;
    cursor: pointer !important;
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
}

[data-testid="stCheckbox"] label span,
[data-testid="stCheckbox"] label p {
    color: #0F172A !important;
    font-size: 0.92rem !important;
    line-height: 1.4 !important;
}

/* Ô vuông của checkbox khi chưa tick (Unchecked) - Chống nền đen do browser Dark mode */
[data-testid="stCheckbox"] label > div:first-child,
[data-testid="stCheckbox"] div[class*="e15oan335"],
[data-testid="stCheckbox"] span[class*="e15oan335"],
[data-testid="stCheckbox"] [role="checkbox"] {
    background-color: #FFFFFF !important;
    background: #FFFFFF !important;
    border: 1.5px solid #94A3B8 !important;
    border-radius: 4px !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05) !important;
    transition: all 0.15s ease !important;
}

/* Hiệu ứng khi rê chuột vào checkbox */
[data-testid="stCheckbox"]:hover label > div:first-child,
[data-testid="stCheckbox"]:hover div[class*="e15oan335"],
[data-testid="stCheckbox"]:hover [role="checkbox"] {
    border-color: #475569 !important;
    background-color: #F8FAFC !important;
}

/* Ô vuông của checkbox khi đã tick (Checked) */
[data-testid="stCheckbox"] div[data-selected="true"] label > div:first-child,
[data-testid="stCheckbox"] label[data-selected="true"] > div:first-child,
[data-testid="stCheckbox"] label[data-checked="true"] > div:first-child,
[data-testid="stCheckbox"] div[aria-checked="true"],
[data-testid="stCheckbox"] input[type="checkbox"]:checked ~ div,
[data-testid="stCheckbox"] input[type="checkbox"]:checked + div {
    background-color: #2563EB !important;
    background: #2563EB !important;
    border-color: #2563EB !important;
}

/* Biểu tượng dấu kiểm (Checkmark polyline / svg) */
[data-testid="stCheckbox"] svg,
[data-testid="stCheckbox"] polyline {
    stroke: #FFFFFF !important;
    stroke-width: 2 !important;
    fill: none !important;
}

/* Nút bấm (Buttons) */
/* Nút phụ / Mặc định (Secondary) */
[data-testid="stMain"] div[data-testid="stButton"] > button:not([kind="primary"]),
[data-testid="stMain"] div[data-testid="stDownloadButton"] > button {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: 0.92rem !important;
    padding: 8px 16px !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
    transition: all 0.15s ease !important;
}

[data-testid="stMain"] div[data-testid="stButton"] > button:not([kind="primary"]) *,
[data-testid="stMain"] div[data-testid="stDownloadButton"] > button * {
    color: #0F172A !important;
}

[data-testid="stMain"] div[data-testid="stButton"] > button:not([kind="primary"]):hover,
[data-testid="stMain"] div[data-testid="stDownloadButton"] > button:hover {
    background-color: #F1F5F9 !important;
    border-color: #94A3B8 !important;
    color: #0F172A !important;
}

/* Nút chính (Primary) - Đồng bộ màu Accent Blue #2563EB, chữ trắng sắc nét không bị chìm */
[data-testid="stMain"] div[data-testid="stButton"] > button[kind="primary"],
[data-testid="stMain"] div[data-testid="stButton"] > button[data-testid="stBaseButton-primary"] {
    background-color: #2563EB !important;
    color: #FFFFFF !important;
    border: 1px solid #1D4ED8 !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    padding: 9px 18px !important;
    box-shadow: 0 1px 3px rgba(37, 99, 235, 0.2) !important;
    transition: all 0.15s ease !important;
}

[data-testid="stMain"] div[data-testid="stButton"] > button[kind="primary"] *,
[data-testid="stMain"] div[data-testid="stButton"] > button[data-testid="stBaseButton-primary"] *,
[data-testid="stMain"] div[data-testid="stButton"] > button[kind="primary"] p,
[data-testid="stMain"] div[data-testid="stButton"] > button[data-testid="stBaseButton-primary"] p {
    color: #FFFFFF !important;
    font-weight: 600 !important;
}

[data-testid="stMain"] div[data-testid="stButton"] > button[kind="primary"]:hover,
[data-testid="stMain"] div[data-testid="stButton"] > button[data-testid="stBaseButton-primary"]:hover {
    background-color: #1D4ED8 !important;
    border-color: #1E40AF !important;
    color: #FFFFFF !important;
    box-shadow: 0 2px 5px rgba(37, 99, 235, 0.3) !important;
}

[data-testid="stMain"] div[data-testid="stButton"] > button[kind="primary"]:hover *,
[data-testid="stMain"] div[data-testid="stButton"] > button[data-testid="stBaseButton-primary"]:hover * {
    color: #FFFFFF !important;
}

[data-testid="stMain"] div[data-testid="stButton"] > button:disabled,
[data-testid="stMain"] div[data-testid="stButton"] > button[disabled] {
    background-color: #F1F5F9 !important;
    border-color: #E2E8F0 !important;
    color: #94A3B8 !important;
    cursor: not-allowed !important;
    box-shadow: none !important;
}

[data-testid="stMain"] div[data-testid="stButton"] > button:disabled *,
[data-testid="stMain"] div[data-testid="stButton"] > button[disabled] * {
    color: #94A3B8 !important;
}

/* Khối Code (st.code) - Xóa bỏ nền đen mặc định, áp dụng nền sáng Soft Slate */
[data-testid="stCode"],
[data-testid="stCode"] pre,
[data-testid="stCode"] code,
.stCode,
.stCode pre,
.stCode code {
    background-color: #F8FAFC !important;
    color: #0F172A !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
    font-size: 0.88rem !important;
    line-height: 1.5 !important;
}

[data-testid="stCode"] pre {
    padding: 10px 14px !important;
    margin: 0 !important;
}

[data-testid="stCode"] code span {
    color: #0F172A !important;
}

[data-testid="stCode"] button {
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    color: #64748B !important;
    border-radius: 6px !important;
}

[data-testid="stCode"] button:hover {
    background-color: #F1F5F9 !important;
    color: #0F172A !important;
}

/* Textarea (st.text_area) - Đặc biệt là khối System Prompt Read-only */
[data-testid="stTextArea"] textarea {
    background-color: #F8FAFC !important;
    color: #0F172A !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
    font-size: 0.88rem !important;
    line-height: 1.55 !important;
}

[data-testid="stTextArea"] textarea:disabled {
    background-color: #F8FAFC !important;
    color: #0F172A !important;
    -webkit-text-fill-color: #0F172A !important;
    opacity: 1 !important;
    cursor: default !important;
    border: 1px solid #E2E8F0 !important;
}

/* File Uploader (st.file_uploader) */
[data-testid="stFileUploader"] {
    margin-bottom: 1rem !important;
}

[data-testid="stFileUploader"] > label {
    color: #0F172A !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    margin-bottom: 0.4rem !important;
}

[data-testid="stFileUploaderDropzone"] {
    background-color: #F8FAFC !important;
    border: 2px dashed #CBD5E1 !important;
    border-radius: 12px !important;
    padding: 1.5rem 1rem !important;
    text-align: center !important;
    transition: all 0.15s ease !important;
}

[data-testid="stFileUploaderDropzone"]:hover {
    border-color: #94A3B8 !important;
    background-color: #F1F5F9 !important;
}

[data-testid="stFileUploaderDropzone"] [data-testid="stMarkdownContainer"] p {
    color: #334155 !important;
    font-size: 0.9rem !important;
}

[data-testid="stFileUploaderDropzone"] button {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    padding: 6px 14px !important;
}

[data-testid="stFileUploaderDropzone"] button:hover {
    background-color: #F1F5F9 !important;
    border-color: #94A3B8 !important;
}

/* Dataframe & Bảng biểu (st.dataframe) */
[data-testid="stDataFrame"],
[data-testid="stDataFrame"] > div,
[data-testid="stDataFrame"] [data-testid="glideDataEditor"],
.stDataFrame {
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
    overflow: hidden !important;
    background-color: #FFFFFF !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
}

[data-testid="stDataFrame"] canvas {
    background-color: #FFFFFF !important;
    border-radius: 8px !important;
}

/* Thẻ Metric Widgets (st.metric) */
[data-testid="stMetric"] {
    background-color: #F8FAFC !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 10px !important;
    padding: 12px 14px !important;
}

[data-testid="stMetricLabel"] {
    color: #64748B !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
}

[data-testid="stMetricLabel"] p {
    color: #64748B !important;
}

[data-testid="stMetricValue"] {
    color: #0F172A !important;
    font-size: 1.35rem !important;
    font-weight: 700 !important;
}

/* Thông báo và Cảnh báo (st.info, st.warning, st.error, st.success) */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    padding: 12px 16px !important;
    font-size: 0.92rem !important;
    line-height: 1.55 !important;
}

div[data-testid="stAlert"]:has([data-testid="stNotificationContentSuccess"]),
div[data-baseweb="notification"][kind="positive"] {
    background-color: #F0FDF4 !important;
    border: 1px solid #BBF7D0 !important;
    color: #15803D !important;
}

div[data-testid="stAlert"]:has([data-testid="stNotificationContentInfo"]),
div[data-baseweb="notification"][kind="info"] {
    background-color: #F0F9FF !important;
    border: 1px solid #BAE6FD !important;
    color: #0369A1 !important;
}

div[data-testid="stAlert"]:has([data-testid="stNotificationContentWarning"]),
div[data-baseweb="notification"][kind="warning"] {
    background-color: #FFFBEB !important;
    border: 1px solid #FDE68A !important;
    color: #92400E !important;
}

div[data-testid="stAlert"]:has([data-testid="stNotificationContentError"]),
div[data-baseweb="notification"][kind="negative"] {
    background-color: #FEF2F2 !important;
    border: 1px solid #FECACA !important;
    color: #B91C1C !important;
}

[data-testid="stAlert"] p, [data-testid="stAlert"] span {
    color: inherit !important;
}

/* Thanh Tiến Trình (st.progress) */
[data-testid="stProgress"] > div > div > div > div {
    background-color: #2563EB !important;
    border-radius: 9999px !important;
}

[data-testid="stProgress"] > div > div > div {
    background-color: #E2E8F0 !important;
    border-radius: 9999px !important;
}

[data-testid="stProgress"] p {
    color: #334155 !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
}

/* ==========================================================================
   6. TỐI ƯU RESPONSIVE MÀN HÌNH NHỎ (< 768px)
   ========================================================================== */
@media (max-width: 768px) {
    .block-container {
        padding-left: 0.85rem !important;
        padding-right: 0.85rem !important;
        padding-top: 0.85rem !important;
        padding-bottom: 6.5rem !important;
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

    [data-testid="stChatMessage"] [data-testid="stVerticalBlockBorderWrapper"] {
        min-width: unset !important;
        max-width: 100% !important;
    }
}
/* ==========================================================================
   7. PHẦN TỬ GIAO DIỆN XÁC THỰC & QUẢN TRỊ TÀI KHOẢN (AUTH & RBAC UI)
   ========================================================================== */
.auth-wrapper {
    max-width: 480px;
    margin: 2rem auto;
    padding: 2.2rem 2.4rem;
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 14px;
    box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.06);
}

.auth-header {
    text-align: center;
    margin-bottom: 1.8rem;
}

.auth-title {
    font-size: 1.55rem;
    font-weight: 700;
    color: #0F172A;
    margin-bottom: 0.35rem;
}

.auth-subtitle {
    font-size: 0.92rem;
    color: #64748B;
}

.sidebar-user-card {
    padding: 10px 12px;
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    margin-bottom: 12px;
}

.sidebar-user-name {
    font-weight: 600;
    font-size: 0.94rem;
    color: #0F172A;
    line-height: 1.3;
}

.sidebar-user-sub {
    font-size: 0.8rem;
    color: #64748B;
    margin-top: 2px;
}

.role-badge-user {
    display: inline-block;
    padding: 2px 7px;
    font-size: 0.72rem;
    font-weight: 600;
    border-radius: 9999px;
    background: #EFF6FF;
    color: #2563EB;
    border: 1px solid #BFDBFE;
}

.role-badge-admin {
    display: inline-block;
    padding: 2px 7px;
    font-size: 0.72rem;
    font-weight: 600;
    border-radius: 9999px;
    background: #FAF5FF;
    color: #7C3AED;
    border: 1px solid #E9D5FF;
}

.conv-history-list {
    max-height: 240px;
    overflow-y: auto;
    margin-bottom: 10px;
}
</style>
"""
