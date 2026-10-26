"""Theme và CSS tùy biến giao diện Chatbox 2.0 theo phong cách ChatGPT (Dark Theme).

Bố cục chuẩn ChatGPT:
- Nền tối trung tính (#212121) cho khung chat chính, sidebar màu tối hơn (#171717).
- Sidebar bên trái: Logo & New Chat button ở đầu, lịch sử phân nhóm thời gian cuộn độc lập ở giữa,
  khu vực tài khoản & cài đặt ghim cố định ở cuối.
- Khung hội thoại trung tâm rộng rãi, giới hạn độ rộng đọc tối ưu (~820px).
- Lượt chat người dùng căn phải với bong bóng tối bo tròn (#2F2F2F).
- Lượt chat trợ lý hiển thị trực tiếp trên nền với typography chuẩn Markdown, không lạm dụng viền card đậm.
- Ô nhập câu hỏi st.chat_input bo tròn 24px, cố định đáy màn hình với nền #2F2F2F.
- Màn hình chào mừng với 4 thẻ gợi ý tương tác hữu ích.
"""

PALETTE = {
    "bg_main": "#212121",           # Nền chính khung chat
    "bg_sidebar": "#171717",        # Nền sidebar bên trái
    "bg_surface": "#2F2F2F",        # Nền bề mặt ô nhập, bong bóng chat, thẻ card
    "bg_hover": "#2A2A2A",          # Trạng thái hover
    "border_subtle": "#2F2F2F",     # Đường viền mờ tinh tế
    "border_medium": "#383838",     # Đường viền phân cách
    "text_primary": "#ECECEC",      # Chữ chính sáng rõ, chống mỏi mắt
    "text_secondary": "#B4B4B4",    # Chữ phụ, caption
    "text_muted": "#8E8E8E",        # Chữ mờ, placeholder
    "accent": "#10A37F",            # Điểm nhấn màu xanh ChatGPT
    "accent_hover": "#0E906F",      # Hover điểm nhấn
    "user_bubble": "#2F2F2F",       # Bong bóng người dùng
    "danger": "#EF4444",            # Màu cảnh báo / xóa
}

CUSTOM_CSS = """
<style>
/* ==========================================================================
   1. GHI ĐÈ BIẾN TOÀN CỤC & DARK THEME CHUẨN CHATGPT
   ========================================================================== */
:root {
    --text-color: #ECECEC !important;
    --background-color: #212121 !important;
    --secondary-background-color: #171717 !important;
    --primary-color: #10A37F !important;
}

/* Áp dụng nền và chữ tối cho toàn bộ ứng dụng */
.stApp {
    background-color: #212121 !important;
    color: #ECECEC !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
    overflow-x: hidden !important;
}

/* Đảm bảo văn bản markdown có độ tương phản và khoảng cách đọc tối ưu */
.stMarkdown p, .stMarkdown li, [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li {
    color: #ECECEC;
    line-height: 1.65;
    font-size: 0.98rem;
}

.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {
    color: #FFFFFF !important;
    font-weight: 600 !important;
}

/* Giới hạn độ rộng vùng đọc trung tâm như ChatGPT */
.block-container {
    max-width: 840px !important;
    width: 100% !important;
    padding-top: 1.2rem !important;
    padding-bottom: 7rem !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
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
   2. KHÓA BỐ CỤC SIDEBAR & VÔ HIỆU HÓA THANH KÉO RESIZE
   ========================================================================== */
/* Vô hiệu hóa tay nắm kéo thay đổi kích thước sidebar */
[data-testid="stSidebar"] .react-resizable-handle,
[data-testid="stSidebarResizeHandle"],
div[data-testid="stSidebarResizeHandle"],
.stSidebar > div[data-testid="stSidebarResizeHandle"],
.stSidebar > div[style*="col-resize"] {
    display: none !important;
    visibility: hidden !important;
    pointer-events: none !important;
    width: 0 !important;
    height: 0 !important;
}

/* Khóa chiều rộng sidebar ở 260px và nền #171717 */
section[data-testid="stSidebar"] {
    background-color: #171717 !important;
    border-right: 1px solid #2F2F2F !important;
    overflow: hidden !important;
}

section[data-testid="stSidebar"][aria-expanded="true"] {
    width: 260px !important;
    min-width: 260px !important;
    max-width: 260px !important;
    flex: 0 0 260px !important;
}

/* Khóa cuộn của container sidebar cha, tổ chức theo Flexbox toàn vẹn:
   - stSidebarContent: full viewport height, overflow hidden
   - stSidebarUserContent: flex column, full height
   - stVerticalBlock: flex column, chia làm 3 phân vùng (Top, History, Footer)
*/
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
    display: flex !important;
    flex-direction: column !important;
    height: 100vh !important;
    max-height: 100vh !important;
    overflow: hidden !important;
    padding: 0 !important;
}

section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
    display: flex !important;
    flex-direction: column !important;
    height: 100% !important;
    max-height: 100% !important;
    overflow: hidden !important;
    padding: 0 !important;
    flex: 1 1 100% !important;
}

section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] > div[data-testid="stVerticalBlock"] {
    display: flex !important;
    flex-direction: column !important;
    height: 100% !important;
    max-height: 100% !important;
    overflow: hidden !important;
    gap: 0 !important;
    flex: 1 1 100% !important;
}

/* ==========================================================================
   3. PHẦN TỬ SIDEBAR: 3 KHU VỰC ĐỘC LẬP (TOP, HISTORY, PINNED FOOTER)
   ========================================================================== */
/* 3.1. KHU VỰC ĐẦU SIDEBAR (st-key-sidebar_top) - CHIỀU CAO TỰ NHIÊN */
section[data-testid="stSidebar"] div[class*="st-key-sidebar_top"],
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] > div[data-testid="stVerticalBlock"] > div:nth-child(1) {
    flex: 0 0 auto !important;
    padding: 0.75rem 0.65rem 0.35rem 0.65rem !important;
}

.sidebar-header-box {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 6px 10px 6px;
}

.sidebar-app-icon {
    font-size: 1.35rem;
    line-height: 1;
}

.sidebar-app-title {
    font-size: 1.12rem;
    font-weight: 600;
    color: #ECECEC;
    letter-spacing: -0.01em;
}

/* Nút tạo cuộc trò chuyện mới (+ Đoạn chat mới) */
.stButton > button[key="btn_sidebar_new_chat"] {
    background-color: #212121 !important;
    color: #ECECEC !important;
    border: 1px solid #2F2F2F !important;
    border-radius: 10px !important;
    padding: 8px 12px !important;
    font-size: 0.92rem !important;
    font-weight: 500 !important;
    text-align: left !important;
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
    transition: all 0.15s ease !important;
    width: 100% !important;
    margin-bottom: 8px !important;
}

.stButton > button[key="btn_sidebar_new_chat"]:hover {
    background-color: #2F2F2F !important;
    border-color: #383838 !important;
    color: #FFFFFF !important;
}

/* 3.2. KHU VỰC LỊCH SỬ Ở GIỮA (st-key-sidebar_history) - CHIẾM KHÔNG GIAN CÒN LẠI & CUỘN ĐỘC LẬP */
section[data-testid="stSidebar"] div[class*="st-key-sidebar_history"],
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] > div[data-testid="stVerticalBlock"] > div:nth-child(2) {
    flex: 1 1 auto !important;
    min-height: 0 !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    padding: 0.25rem 0.65rem 0.5rem 0.65rem !important;
    scrollbar-width: thin !important;
    scrollbar-color: #2F2F2F transparent !important;
}

/* Thanh cuộn siêu mảnh tối giản */
section[data-testid="stSidebar"] div[class*="st-key-sidebar_history"]::-webkit-scrollbar {
    width: 4px !important;
}

section[data-testid="stSidebar"] div[class*="st-key-sidebar_history"]::-webkit-scrollbar-track {
    background: transparent !important;
}

section[data-testid="stSidebar"] div[class*="st-key-sidebar_history"]::-webkit-scrollbar-thumb {
    background: #2F2F2F !important;
    border-radius: 4px !important;
}

section[data-testid="stSidebar"] div[class*="st-key-sidebar_history"]::-webkit-scrollbar-thumb:hover {
    background: #383838 !important;
}

/* Tiêu đề nhóm thời gian trong lịch sử (Hôm nay, 7 ngày gần đây, Trước đó) */
.history-time-heading {
    font-size: 0.72rem;
    font-weight: 600;
    color: #8E8E8E;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 8px 6px 4px 6px;
    margin-top: 4px;
}

/* Nút từng cuộc trò chuyện trong lịch sử */
div[data-testid="stSidebar"] div.stButton > button[key^="btn_conv_"] {
    background-color: transparent !important;
    color: #B4B4B4 !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 7px 10px !important;
    font-size: 0.88rem !important;
    font-weight: 400 !important;
    text-align: left !important;
    width: 100% !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    margin-bottom: 2px !important;
    transition: background-color 0.15s ease, color 0.15s ease !important;
}

div[data-testid="stSidebar"] div.stButton > button[key^="btn_conv_"]:hover {
    background-color: #212121 !important;
    color: #ECECEC !important;
}

/* Mục hội thoại đang mở (active) */
div[data-testid="stSidebar"] div.stButton > button[key^="btn_conv_active_"] {
    background-color: #212121 !important;
    color: #FFFFFF !important;
    font-weight: 500 !important;
    border: 1px solid #2F2F2F !important;
}

/* 3.3. KHU VỰC TÀI KHOẢN & CÀI ĐẶT GHIM Ở ĐÁY SIDEBAR (st-key-sidebar_footer) */
section[data-testid="stSidebar"] div[class*="st-key-sidebar_footer"],
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] > div[data-testid="stVerticalBlock"] > div:nth-child(3) {
    flex: 0 0 auto !important;
    margin-top: auto !important;
    padding: 0.65rem 0.65rem 0.75rem 0.65rem !important;
    border-top: 1px solid #2F2F2F !important;
    background-color: #171717 !important;
    z-index: 10 !important;
}

/* Nút popover tài khoản ở chân sidebar */
[data-testid="stSidebar"] [data-testid="stPopover"] > button {
    background-color: #212121 !important;
    color: #ECECEC !important;
    border: 1px solid #2F2F2F !important;
    border-radius: 10px !important;
    padding: 8px 10px !important;
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    width: 100% !important;
    text-align: left !important;
    display: flex !important;
    align-items: center !important;
    justify-content: flex-start !important;
    gap: 8px !important;
    transition: background-color 0.15s ease, border-color 0.15s ease !important;
}

[data-testid="stSidebar"] [data-testid="stPopover"] > button:hover {
    background-color: #2A2A2A !important;
    border-color: #383838 !important;
}

/* Nút Đăng nhập & Tạo tài khoản ở footer khi chưa đăng nhập */
.stButton > button[key="btn_sidebar_unauth_login"] {
    background-color: #10A37F !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 7px 12px !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    margin-bottom: 6px !important;
    width: 100% !important;
    transition: background-color 0.15s ease !important;
}

.stButton > button[key="btn_sidebar_unauth_login"]:hover {
    background-color: #0E906F !important;
}

.stButton > button[key="btn_sidebar_unauth_register"] {
    background-color: #212121 !important;
    color: #ECECEC !important;
    border: 1px solid #2F2F2F !important;
    border-radius: 8px !important;
    padding: 7px 12px !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    width: 100% !important;
    transition: background-color 0.15s ease, border-color 0.15s ease !important;
}

.stButton > button[key="btn_sidebar_unauth_register"]:hover {
    background-color: #2A2A2A !important;
    border-color: #383838 !important;
    color: #FFFFFF !important;
}

/* Hộp popover menu tài khoản */
[data-testid="stPopoverBody"] {
    background-color: #171717 !important;
    border: 1px solid #2F2F2F !important;
    border-radius: 12px !important;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5) !important;
    padding: 12px !important;
    color: #ECECEC !important;
    z-index: 999999 !important;
    max-height: calc(100vh - 80px) !important;
    overflow-y: auto !important;
}

[data-testid="stPopoverBody"] hr {
    border-color: #2F2F2F !important;
    margin: 8px 0 !important;
}

/* Badge vai trò */
.role-badge-user {
    display: inline-block;
    padding: 2px 7px;
    font-size: 0.72rem;
    font-weight: 600;
    border-radius: 9999px;
    background: #1E293B;
    color: #38BDF8;
    border: 1px solid #334155;
}

.role-badge-admin {
    display: inline-block;
    padding: 2px 7px;
    font-size: 0.72rem;
    font-weight: 600;
    border-radius: 9999px;
    background: #2E1065;
    color: #C084FC;
    border: 1px solid #4C1D95;
}

/* Trạng thái Ollama ở chân sidebar */
.sidebar-footer-status {
    font-size: 0.78rem;
    padding: 4px 8px;
    border-radius: 6px;
    margin-top: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
}

.sidebar-footer-status.online {
    color: #4ADE80;
}

.sidebar-footer-status.offline {
    color: #F87171;
}

/* ==========================================================================
   5. KHUNG CHAT CHÍNH: HEADER, MÀN HÌNH CHÀO MỪNG VÀ GỢI Ý
   ========================================================================== */
/* Thanh tiêu đề nhỏ ở đầu khung chat */
.chat-top-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0 16px 0;
    margin-bottom: 8px;
    border-bottom: 1px solid #2F2F2F;
}

.chat-top-left {
    display: flex;
    align-items: center;
    gap: 8px;
}

.chat-view-title {
    font-size: 1.15rem;
    font-weight: 600;
    color: #ECECEC;
}

.chat-local-pill {
    font-size: 0.72rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 9999px;
    background: #2F2F2F;
    color: #A3A3A3;
    border: 1px solid #383838;
}

.chat-top-right {
    font-size: 0.82rem;
    color: #8E8E8E;
    display: flex;
    align-items: center;
    gap: 6px;
}

.status-dot.online {
    color: #4ADE80;
}

.status-dot.offline {
    color: #F87171;
}

/* Màn hình chào mừng khi chưa có tin nhắn (Empty State chuẩn ChatGPT) */
.chat-empty-state-box {
    text-align: center;
    padding: 3.5rem 1rem 2rem 1rem;
    max-width: 650px;
    margin: 0 auto;
}

.chat-empty-icon {
    font-size: 2.8rem;
    margin-bottom: 0.75rem;
    display: inline-block;
}

.chat-empty-title {
    font-size: 1.75rem;
    font-weight: 600;
    color: #ECECEC;
    margin-bottom: 0.4rem;
}

.chat-empty-subtitle {
    font-size: 0.95rem;
    color: #8E8E8E;
    line-height: 1.5;
    margin-bottom: 2rem;
}

/* Thẻ gợi ý câu hỏi dạng Grid 2x2 */
.suggestion-card {
    background-color: #212121;
    border: 1px solid #2F2F2F;
    border-radius: 12px;
    padding: 12px 14px;
    cursor: pointer;
    text-align: left;
    transition: background-color 0.15s ease, border-color 0.15s ease;
    margin-bottom: 8px;
}

.suggestion-card:hover {
    background-color: #2A2A2A;
    border-color: #383838;
}

.suggestion-prompt {
    font-size: 0.9rem;
    font-weight: 500;
    color: #ECECEC;
    margin-bottom: 2px;
}

.suggestion-desc {
    font-size: 0.78rem;
    color: #8E8E8E;
}

/* ==========================================================================
   6. BONG BÓNG TIN NHẮN (MESSAGE TURNS CHUẨN CHATGPT)
   ========================================================================== */
/* Bỏ khung st.chat_message mặc định */
[data-testid="stChatMessage"] {
    background-color: transparent !important;
    padding: 12px 0 !important;
    gap: 12px !important;
}

/* Lượt người dùng: căn phải, nền #2F2F2F bo tròn kiểu pill */
.user-turn-wrapper {
    display: flex;
    justify-content: flex-end;
    width: 100%;
}

.user-turn-body {
    background-color: #2F2F2F;
    color: #ECECEC;
    padding: 10px 16px;
    border-radius: 20px;
    max-width: 80%;
    word-break: break-word;
    font-size: 0.98rem;
    line-height: 1.55;
}

/* Lượt trợ lý: đặt trực tiếp trên nền tối, không viền card dày */
.bot-turn-wrapper {
    display: flex;
    gap: 12px;
    width: 100%;
    align-items: flex-start;
}

.bot-avatar-icon {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background-color: #10A37F;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 15px;
    flex-shrink: 0;
    margin-top: 2px;
}

.bot-turn-content {
    flex: 1 1 auto;
    color: #ECECEC;
    font-size: 0.98rem;
    line-height: 1.65;
    word-break: break-word;
}

/* Huy hiệu nguồn dữ liệu (Provenance) */
.source-badge {
    display: inline-block;
    padding: 2px 8px;
    margin-right: 6px;
    margin-bottom: 4px;
    font-size: 0.75rem;
    border-radius: 6px;
    background: #171717;
    border: 1px solid #2F2F2F;
    color: #A3A3A3;
}

/* ==========================================================================
   7. Ô NHẬP LIỆU ST.CHAT_INPUT CHUẨN CHATGPT
   ========================================================================== */
[data-testid="stChatInput"] {
    background-color: #2F2F2F !important;
    border: 1px solid #383838 !important;
    border-radius: 24px !important;
    padding: 4px 8px !important;
    box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.4) !important;
}

[data-testid="stChatInput"] textarea {
    color: #ECECEC !important;
    font-size: 0.96rem !important;
    background-color: transparent !important;
}

[data-testid="stChatInput"] textarea::placeholder {
    color: #8E8E8E !important;
}

[data-testid="stChatInput"] button {
    color: #ECECEC !important;
    background-color: transparent !important;
    border-radius: 50% !important;
    transition: background-color 0.15s ease !important;
}

[data-testid="stChatInput"] button:hover {
    background-color: #383838 !important;
}

/* Chú thích nguồn dữ liệu ở đáy khung chat */
.chat-bottom-status-line {
    text-align: center;
    font-size: 0.75rem;
    color: #8E8E8E;
    margin-top: 8px;
    padding-bottom: 4px;
}

/* ==========================================================================
   8. CÁC THÀNH PHẦN QUẢN TRỊ & FORM DARK THEME
   ========================================================================== */
/* Container có viền (st.container(border=True)) */
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #171717 !important;
    border: 1px solid #2F2F2F !important;
    border-radius: 12px !important;
}

/* Input, Selectbox, Textarea */
.stTextInput > div > div > input,
.stSelectbox > div > div,
.stTextArea > div > div > textarea {
    background-color: #212121 !important;
    color: #ECECEC !important;
    border: 1px solid #2F2F2F !important;
    border-radius: 8px !important;
}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #10A37F !important;
    box-shadow: 0 0 0 1px #10A37F !important;
}

/* Bảng st.dataframe */
[data-testid="stDataFrame"] {
    background-color: #171717 !important;
    border: 1px solid #2F2F2F !important;
    border-radius: 8px !important;
}

/* Tabs */
button[data-baseweb="tab"] {
    color: #8E8E8E !important;
    background-color: transparent !important;
    font-weight: 500 !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    color: #ECECEC !important;
    border-bottom-color: #10A37F !important;
}

/* Metric cards */
div[data-testid="stMetricValue"] {
    color: #FFFFFF !important;
    font-weight: 600 !important;
}

div[data-testid="stMetricLabel"] {
    color: #8E8E8E !important;
}

/* Thông báo st.info, st.success, st.warning, st.error */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    padding: 10px 14px !important;
    font-size: 0.92rem !important;
}

div[data-testid="stAlert"]:has([data-testid="stNotificationContentSuccess"]) {
    background-color: #064E3B !important;
    border: 1px solid #059669 !important;
    color: #A7F3D0 !important;
}

div[data-testid="stAlert"]:has([data-testid="stNotificationContentInfo"]) {
    background-color: #1E293B !important;
    border: 1px solid #334155 !important;
    color: #BAE6FD !important;
}

div[data-testid="stAlert"]:has([data-testid="stNotificationContentWarning"]) {
    background-color: #451A03 !important;
    border: 1px solid #D97706 !important;
    color: #FDE68A !important;
}

div[data-testid="stAlert"]:has([data-testid="stNotificationContentError"]) {
    background-color: #450A0A !important;
    border: 1px solid #DC2626 !important;
    color: #FECACA !important;
}

[data-testid="stAlert"] p, [data-testid="stAlert"] span {
    color: inherit !important;
}

/* ==========================================================================
   9. TỐI ƯU RESPONSIVE MÀN HÌNH NHỎ (< 768px)
   ========================================================================== */
@media (max-width: 768px) {
    .block-container {
        padding-left: 0.85rem !important;
        padding-right: 0.85rem !important;
        padding-top: 0.85rem !important;
        padding-bottom: 6.5rem !important;
    }
    
    .chat-view-title {
        font-size: 1.05rem !important;
    }
    
    .user-turn-body {
        max-width: 90% !important;
    }
}
</style>
"""
