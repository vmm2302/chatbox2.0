"""Theme và CSS tùy biến giao diện Chatbox 2.0 theo phong cách ChatGPT (System / Light & Dark Theme).

Hỗ trợ đồng bộ giao diện theo thiết bị (System theme):
- Chế độ sáng (Light): Nền trắng trung tính (#FFFFFF) cho khung chat chính, sidebar màu xám nhạt (#F9F9F9),
  bong bóng chat người dùng (#F4F4F4), chữ đậm tương phản cao (#0D0D0D).
- Chế độ tối (Dark): Nền tối trung tính (#212121) cho khung chat chính, sidebar màu tối hơn (#171717),
  bong bóng chat người dùng (#2F2F2F), chữ sáng dịu (#ECECEC).
- Bố cục chuẩn ChatGPT:
  + Sidebar bên trái: Logo & New Chat button ở đầu, lịch sử phân nhóm thời gian cuộn độc lập ở giữa,
    khu vực tài khoản & cài đặt ghim cố định ở cuối.
  + Khung hội thoại trung tâm rộng rãi, giới hạn độ rộng đọc tối ưu (~840px).
  + Lượt chat người dùng căn phải với bong bóng bo tròn kiểu pill.
  + Lượt chat trợ lý hiển thị trực tiếp trên nền với typography chuẩn Markdown.
  + Ô nhập câu hỏi st.chat_input bo tròn 24px, căn giữa theo khung chat.
  + Màn hình chào mừng với 4 thẻ gợi ý tương tác hữu ích.
"""

from typing import Optional


LIGHT_PALETTE = {
    "bg_main": "#FFFFFF",
    "bg_sidebar": "#F9F9F9",
    "bg_surface": "#FFFFFF",
    "bg_hover": "#F0F0F0",
    "border_subtle": "#E5E5E5",
    "border_medium": "#D1D5DB",
    "text_primary": "#0D0D0D",
    "text_secondary": "#555555",
    "text_muted": "#8E8E8E",
    "accent": "#10A37F",
    "accent_hover": "#0E906F",
    "user_bubble": "#F4F4F4",
    "danger": "#EF4444",
}

DARK_PALETTE = {
    "bg_main": "#212121",
    "bg_sidebar": "#171717",
    "bg_surface": "#2F2F2F",
    "bg_hover": "#2A2A2A",
    "border_subtle": "#2F2F2F",
    "border_medium": "#383838",
    "text_primary": "#ECECEC",
    "text_secondary": "#B4B4B4",
    "text_muted": "#8E8E8E",
    "accent": "#10A37F",
    "accent_hover": "#0E906F",
    "user_bubble": "#2F2F2F",
    "danger": "#EF4444",
}

# Giữ tương thích ngược với code cũ import PALETTE
PALETTE = DARK_PALETTE


def get_custom_css(theme_type: Optional[str] = None) -> str:
    """Tạo mã CSS tùy biến thích ứng với theme thiết bị (System), Light hoặc Dark."""
    dark_explicit_rule = ""
    light_explicit_rule = ""

    if theme_type == "dark":
        dark_explicit_rule = """
        :root {
            --app-bg: #212121 !important;
            --sidebar-bg: #171717 !important;
            --surface-bg: #2F2F2F !important;
            --surface-hover: #2A2A2A !important;
            --border-subtle: #2F2F2F !important;
            --border-medium: #383838 !important;
            --text-primary: #ECECEC !important;
            --text-secondary: #B4B4B4 !important;
            --text-muted: #8E8E8E !important;
            --user-bubble-bg: #2F2F2F !important;
            --user-bubble-text: #ECECEC !important;
            --chat-input-bg: #2F2F2F !important;
            --chat-input-border: #383838 !important;
            --chat-input-placeholder: #8E8E8E !important;
            --popover-bg: #171717 !important;
            --card-bg: #212121 !important;
            --card-border: #2F2F2F !important;
            --active-item-bg: #212121 !important;
            --active-item-text: #FFFFFF !important;
            --source-badge-bg: #171717 !important;
            --source-badge-border: #2F2F2F !important;
            --source-badge-text: #10A37F !important;
            --danger-bg: #3F1D1D !important;
            --danger-text: #EF4444 !important;
            --shadow-popover: 0 10px 25px -5px rgba(0, 0, 0, 0.5) !important;
            --shadow-chat-input: 0 4px 20px -2px rgba(0, 0, 0, 0.4) !important;
            --alert-success-bg: #064E3B !important;
            --alert-success-border: #059669 !important;
            --alert-success-text: #A7F3D0 !important;
            --alert-info-bg: #1E293B !important;
            --alert-info-border: #334155 !important;
            --alert-info-text: #BAE6FD !important;
            --alert-warning-bg: #451A03 !important;
            --alert-warning-border: #D97706 !important;
            --alert-warning-text: #FDE68A !important;
            --alert-error-bg: #450A0A !important;
            --alert-error-border: #DC2626 !important;
            --alert-error-text: #FECACA !important;
        }
        """
    elif theme_type == "light":
        light_explicit_rule = """
        :root {
            --app-bg: #FFFFFF !important;
            --sidebar-bg: #F9F9F9 !important;
            --surface-bg: #FFFFFF !important;
            --surface-hover: #F0F0F0 !important;
            --border-subtle: #E5E5E5 !important;
            --border-medium: #D1D5DB !important;
            --text-primary: #0D0D0D !important;
            --text-secondary: #555555 !important;
            --text-muted: #8E8E8E !important;
            --user-bubble-bg: #F4F4F4 !important;
            --user-bubble-text: #0D0D0D !important;
            --chat-input-bg: #FFFFFF !important;
            --chat-input-border: #E5E5E5 !important;
            --chat-input-placeholder: #8E8E8E !important;
            --popover-bg: #FFFFFF !important;
            --card-bg: #FFFFFF !important;
            --card-border: #E5E5E5 !important;
            --active-item-bg: #EAEAEA !important;
            --active-item-text: #0D0D0D !important;
            --source-badge-bg: #F0FDF4 !important;
            --source-badge-border: #DCFCE7 !important;
            --source-badge-text: #10A37F !important;
            --danger-bg: #FEE2E2 !important;
            --danger-text: #DC2626 !important;
            --shadow-popover: 0 10px 25px -5px rgba(0, 0, 0, 0.1) !important;
            --shadow-chat-input: 0 4px 20px -2px rgba(0, 0, 0, 0.08) !important;
            --alert-success-bg: #ECFDF5 !important;
            --alert-success-border: #A7F3D0 !important;
            --alert-success-text: #065F46 !important;
            --alert-info-bg: #F0F9FF !important;
            --alert-info-border: #BAE6FD !important;
            --alert-info-text: #0369A1 !important;
            --alert-warning-bg: #FFFBEB !important;
            --alert-warning-border: #FDE68A !important;
            --alert-warning-text: #92400E !important;
            --alert-error-bg: #FEF2F2 !important;
            --alert-error-border: #FECACA !important;
            --alert-error-text: #991B1B !important;
        }
        """

    return f"""
<style>
/* ==========================================================================
   1. HỆ THỐNG BIẾN TOÀN CỤC CHUẨN SYSTEM / LIGHT / DARK THEME
   ========================================================================== */
:root {{
    /* Điểm nhấn thương hiệu OpenAI ChatGPT */
    --accent: #10A37F;
    --accent-hover: #0E906F;
    --danger: #EF4444;
    --danger-bg: #FEE2E2;
    --danger-text: #DC2626;

    /* Theme Sáng (Light - Mặc định khi thiết bị ở chế độ sáng) */
    --app-bg: #FFFFFF;
    --sidebar-bg: #F9F9F9;
    --surface-bg: #FFFFFF;
    --surface-hover: #F0F0F0;
    --border-subtle: #E5E5E5;
    --border-medium: #D1D5DB;
    --text-primary: #0D0D0D;
    --text-secondary: #555555;
    --text-muted: #8E8E8E;
    --user-bubble-bg: #F4F4F4;
    --user-bubble-text: #0D0D0D;
    --chat-input-bg: #FFFFFF;
    --chat-input-border: #E5E5E5;
    --chat-input-placeholder: #8E8E8E;
    --popover-bg: #FFFFFF;
    --card-bg: #FFFFFF;
    --card-border: #E5E5E5;
    --active-item-bg: #EAEAEA;
    --active-item-text: #0D0D0D;
    --source-badge-bg: #F0FDF4;
    --source-badge-border: #DCFCE7;
    --source-badge-text: #10A37F;
    --shadow-popover: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
    --shadow-chat-input: 0 4px 20px -2px rgba(0, 0, 0, 0.08);

    --alert-success-bg: #ECFDF5;
    --alert-success-border: #A7F3D0;
    --alert-success-text: #065F46;
    --alert-info-bg: #F0F9FF;
    --alert-info-border: #BAE6FD;
    --alert-info-text: #0369A1;
    --alert-warning-bg: #FFFBEB;
    --alert-warning-border: #FDE68A;
    --alert-warning-text: #92400E;
    --alert-error-bg: #FEF2F2;
    --alert-error-border: #FECACA;
    --alert-error-text: #991B1B;
}}

/* Chế độ Dark Theme theo thiết lập hệ điều hành / thiết bị (prefers-color-scheme: dark) */
@media (prefers-color-scheme: dark) {{
    :root {{
        --app-bg: #212121;
        --sidebar-bg: #171717;
        --surface-bg: #2F2F2F;
        --surface-hover: #2A2A2A;
        --border-subtle: #2F2F2F;
        --border-medium: #383838;
        --text-primary: #ECECEC;
        --text-secondary: #B4B4B4;
        --text-muted: #8E8E8E;
        --user-bubble-bg: #2F2F2F;
        --user-bubble-text: #ECECEC;
        --chat-input-bg: #2F2F2F;
        --chat-input-border: #383838;
        --chat-input-placeholder: #8E8E8E;
        --popover-bg: #171717;
        --card-bg: #212121;
        --card-border: #2F2F2F;
        --active-item-bg: #212121;
        --active-item-text: #FFFFFF;
        --source-badge-bg: #171717;
        --source-badge-border: #2F2F2F;
        --source-badge-text: #10A37F;
        --danger-bg: #3F1D1D;
        --danger-text: #EF4444;
        --shadow-popover: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        --shadow-chat-input: 0 4px 20px -2px rgba(0, 0, 0, 0.4);

        --alert-success-bg: #064E3B;
        --alert-success-border: #059669;
        --alert-success-text: #A7F3D0;
        --alert-info-bg: #1E293B;
        --alert-info-border: #334155;
        --alert-info-text: #BAE6FD;
        --alert-warning-bg: #451A03;
        --alert-warning-border: #D97706;
        --alert-warning-text: #FDE68A;
        --alert-error-bg: #450A0A;
        --alert-error-border: #DC2626;
        --alert-error-text: #FECACA;
    }}
}}

{dark_explicit_rule}
{light_explicit_rule}

/* Áp dụng nền và màu chữ thích ứng cho toàn bộ ứng dụng */
.stApp {{
    background-color: var(--app-bg) !important;
    color: var(--text-primary) !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
    overflow-x: hidden !important;
}}

/* Đảm bảo văn bản markdown có độ tương phản và khoảng cách đọc tối ưu */
.stMarkdown p, .stMarkdown li, [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li {{
    color: var(--text-primary);
    line-height: 1.65;
    font-size: 0.98rem;
}}

.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {{
    color: var(--text-primary) !important;
    font-weight: 600 !important;
}}

/* Giới hạn độ rộng vùng đọc trung tâm như ChatGPT */
.block-container {{
    max-width: 840px !important;
    width: 100% !important;
    padding-top: 1.2rem !important;
    padding-bottom: 7rem !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    margin: 0 auto !important;
    box-sizing: border-box !important;
}}

/* Ẩn ba biểu tượng Streamlit trong header: Deploy, StatusWidget, MainMenu (nhưng GIỮ nút thu gọn và mở sidebar) */
.stDeployButton,
[data-testid="stDeployButton"],
[data-testid="stAppDeployButton"],
[data-testid="stToolbarActions"],
[data-testid="stStatusWidget"],
#MainMenu,
[data-testid="stMainMenu"],
[data-testid="stMainMenuButton"] {{
    visibility: hidden !important;
    display: none !important;
}}

/* Đảm bảo nút thu gọn và nút mở lại sidebar luôn hiển thị và hoạt động trên mọi phiên bản Streamlit */
[data-testid="stSidebarCollapsedControl"],
[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapseButton"] {{
    visibility: visible !important;
    display: flex !important;
}}

footer {{
    visibility: hidden !important;
    display: none !important;
}}

header[data-testid="stHeader"], header[data-testid="stAppHeader"] {{
    background-color: transparent !important;
}}

/* ==========================================================================
   2. KHÓA BỐ CỤC SIDEBAR & VÔ HIỆU HÓA THANH KÉO RESIZE
   ========================================================================== */
/* Vô hiệu hóa tay nắm kéo thay đổi kích thước sidebar */
[data-testid="stSidebar"] .react-resizable-handle,
[data-testid="stSidebarResizeHandle"],
div[data-testid="stSidebarResizeHandle"],
.stSidebar > div[data-testid="stSidebarResizeHandle"],
.stSidebar > div[style*="col-resize"] {{
    display: none !important;
    visibility: hidden !important;
    pointer-events: none !important;
    width: 0 !important;
    height: 0 !important;
}}

/* Khóa chiều rộng sidebar ở 260px và màu nền theo theme */
section[data-testid="stSidebar"] {{
    background-color: var(--sidebar-bg) !important;
    border-right: 1px solid var(--border-subtle) !important;
    overflow: hidden !important;
}}

section[data-testid="stSidebar"][aria-expanded="true"] {{
    width: 260px !important;
    min-width: 260px !important;
    max-width: 260px !important;
    flex: 0 0 260px !important;
}}

section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
    display: flex !important;
    flex-direction: column !important;
    height: 100% !important;
    max-height: 100vh !important;
    overflow: hidden !important;
    padding: 0 !important;
}}

section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{
    display: flex !important;
    flex-direction: column !important;
    height: 100% !important;
    max-height: 100% !important;
    overflow: hidden !important;
    padding: 0 !important;
    flex: 1 1 100% !important;
    min-height: 0 !important;
}}

/* Đảm bảo khối bọc trung gian và khối dọc chính trong stSidebarUserContent mở rộng đủ 100% */
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] > div,
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] > div > div[data-testid="stVerticalBlock"] {{
    display: flex !important;
    flex-direction: column !important;
    height: 100% !important;
    max-height: 100% !important;
    overflow: hidden !important;
    gap: 0 !important;
    flex: 1 1 100% !important;
    min-height: 0 !important;
}}

/* ==========================================================================
   3. PHẦN TỬ SIDEBAR: 3 KHU VỰC ĐỘC LẬP (TOP, HISTORY, PINNED FOOTER)
   ========================================================================== */
/* 3.1. KHU VỰC ĐẦU SIDEBAR (st-key-sidebar_top) - CHIỀU CAO THEO NỘI DUNG */
section[data-testid="stSidebar"] div[data-testid="stLayoutWrapper"]:has(div[class*="st-key-sidebar_top"]),
section[data-testid="stSidebar"] div[class*="st-key-sidebar_top"] {{
    flex: 0 0 auto !important;
    height: auto !important;
}}

section[data-testid="stSidebar"] div[class*="st-key-sidebar_top"] {{
    padding: 0.75rem 0.65rem 0.35rem 0.65rem !important;
}}

.sidebar-header-box {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 6px 10px 6px;
}}

.sidebar-app-icon {{
    font-size: 1.35rem;
    line-height: 1;
}}

.sidebar-app-title {{
    font-size: 1.12rem;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: -0.01em;
}}

/* Nút tạo cuộc trò chuyện mới (+ Đoạn chat mới) */
.stButton > button[key="btn_sidebar_new_chat"] {{
    background-color: var(--card-bg) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-subtle) !important;
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
}}

.stButton > button[key="btn_sidebar_new_chat"]:hover {{
    background-color: var(--surface-hover) !important;
    border-color: var(--border-medium) !important;
    color: var(--text-primary) !important;
}}

/* 3.2. KHU VỰC LỊCH SỬ Ở GIỮA (st-key-sidebar_history) - CHIẾM KHÔNG GIAN CÒN LẠI & CUỘN BÊN TRONG */
section[data-testid="stSidebar"] div[data-testid="stLayoutWrapper"]:has(div[class*="st-key-sidebar_history"]) {{
    flex: 1 1 auto !important;
    min-height: 0 !important;
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden !important;
    height: auto !important;
}}

section[data-testid="stSidebar"] div[class*="st-key-sidebar_history"] {{
    flex: 1 1 100% !important;
    min-height: 0 !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    padding: 0.25rem 0.65rem 0.5rem 0.65rem !important;
    scrollbar-width: thin !important;
    scrollbar-color: var(--border-subtle) transparent !important;
}}

/* Thanh cuộn siêu mảnh tối giản */
section[data-testid="stSidebar"] div[class*="st-key-sidebar_history"]::-webkit-scrollbar {{
    width: 4px !important;
}}

section[data-testid="stSidebar"] div[class*="st-key-sidebar_history"]::-webkit-scrollbar-track {{
    background: transparent !important;
}}

section[data-testid="stSidebar"] div[class*="st-key-sidebar_history"]::-webkit-scrollbar-thumb {{
    background: var(--border-subtle) !important;
    border-radius: 4px !important;
}}

section[data-testid="stSidebar"] div[class*="st-key-sidebar_history"]::-webkit-scrollbar-thumb:hover {{
    background: var(--border-medium) !important;
}}

/* Tiêu đề nhóm thời gian trong lịch sử (Đã ghim, Hôm nay, 7 ngày gần đây, Trước đó) */
.history-time-heading {{
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 8px 6px 4px 6px;
    margin-top: 4px;
}}

/* Nút từng cuộc trò chuyện trong lịch sử */
div[data-testid="stSidebar"] div.stButton > button[key^="btn_conv_"] {{
    background-color: transparent !important;
    color: var(--text-secondary) !important;
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
}}

div[data-testid="stSidebar"] div.stButton > button[key^="btn_conv_"]:hover {{
    background-color: var(--surface-hover) !important;
    color: var(--text-primary) !important;
}}

/* Mục hội thoại đang mở (active) */
div[data-testid="stSidebar"] div.stButton > button[key^="btn_conv_active_"] {{
    background-color: var(--active-item-bg) !important;
    color: var(--active-item-text) !important;
    font-weight: 500 !important;
    border: 1px solid var(--border-subtle) !important;
}}

/* 3.3. KHU VỰC TÀI KHOẢN Ở ĐÁY SIDEBAR (st-key-sidebar_footer) - GHIM SÁT ĐÁY */
section[data-testid="stSidebar"] div[data-testid="stLayoutWrapper"]:has(div[class*="st-key-sidebar_footer"]),
section[data-testid="stSidebar"] div[class*="st-key-sidebar_footer"] {{
    flex: 0 0 auto !important;
    margin-top: auto !important;
    height: auto !important;
}}

section[data-testid="stSidebar"] div[class*="st-key-sidebar_footer"] {{
    padding: 0.65rem 0.65rem 0.75rem 0.65rem !important;
    border-top: 1px solid var(--border-subtle) !important;
    background-color: var(--sidebar-bg) !important;
    z-index: 10 !important;
}}

/* Nút popover tài khoản ở chân sidebar */
[data-testid="stSidebar"] [data-testid="stPopover"] button,
[data-testid="stSidebar"] button[data-testid="stPopoverButton"] {{
    background-color: var(--card-bg) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-subtle) !important;
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
}}

[data-testid="stSidebar"] [data-testid="stPopover"] button:hover,
[data-testid="stSidebar"] button[data-testid="stPopoverButton"]:hover {{
    background-color: var(--surface-hover) !important;
    border-color: var(--border-medium) !important;
}}

/* Nút Đăng nhập & Tạo tài khoản ở footer khi chưa đăng nhập */
.stButton > button[key="btn_sidebar_unauth_login"] {{
    background-color: var(--accent) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 7px 12px !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    margin-bottom: 6px !important;
    width: 100% !important;
    transition: background-color 0.15s ease !important;
}}

.stButton > button[key="btn_sidebar_unauth_login"]:hover {{
    background-color: var(--accent-hover) !important;
}}

.stButton > button[key="btn_sidebar_unauth_register"] {{
    background-color: var(--card-bg) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 8px !important;
    padding: 7px 12px !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    width: 100% !important;
    transition: background-color 0.15s ease, border-color 0.15s ease !important;
}}

.stButton > button[key="btn_sidebar_unauth_register"]:hover {{
    background-color: var(--surface-hover) !important;
    border-color: var(--border-medium) !important;
    color: var(--text-primary) !important;
}}

/* Hộp popover menu tài khoản */
[data-testid="stPopoverBody"] {{
    background-color: var(--popover-bg) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 12px !important;
    box-shadow: var(--shadow-popover) !important;
    padding: 12px !important;
    color: var(--text-primary) !important;
    z-index: 999999 !important;
    max-height: calc(100vh - 80px) !important;
    overflow-y: auto !important;
}}

[data-testid="stPopoverBody"] hr {{
    border-color: var(--border-subtle) !important;
    margin: 8px 0 !important;
}}

/* Badge vai trò */
.role-badge-user {{
    display: inline-block;
    padding: 2px 7px;
    font-size: 0.72rem;
    font-weight: 600;
    border-radius: 9999px;
    background: #E0F2FE;
    color: #0369A1;
    border: 1px solid #BAE6FD;
}}

.role-badge-admin {{
    display: inline-block;
    padding: 2px 7px;
    font-size: 0.72rem;
    font-weight: 600;
    border-radius: 9999px;
    background: #F3E8FF;
    color: #7E22CE;
    border: 1px solid #DDD6FE;
}}

@media (prefers-color-scheme: dark) {{
    .role-badge-user {{
        background: #1E293B;
        color: #38BDF8;
        border: 1px solid #334155;
    }}
    .role-badge-admin {{
        background: #2E1065;
        color: #C084FC;
        border: 1px solid #4C1D95;
    }}
}}

/* ==========================================================================
   4. KHUNG CHAT CHÍNH: HEADER, MÀN HÌNH CHÀO MỪNG VÀ GỢI Ý
   ========================================================================== */
.chat-top-bar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0 16px 0;
    margin-bottom: 8px;
    border-bottom: 1px solid var(--border-subtle);
}}

.chat-top-left {{
    display: flex;
    align-items: center;
    gap: 8px;
}}

.chat-view-title {{
    font-size: 1.15rem;
    font-weight: 600;
    color: var(--text-primary);
}}

.chat-local-pill {{
    font-size: 0.72rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 9999px;
    background: var(--surface-bg);
    color: var(--text-secondary);
    border: 1px solid var(--border-subtle);
}}

.chat-top-right {{
    font-size: 0.82rem;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    gap: 6px;
}}

.status-dot.online {{
    color: #16A34A;
}}

.status-dot.offline {{
    color: #DC2626;
}}

/* Màn hình chào mừng khi chưa có tin nhắn */
.chat-empty-state-box {{
    text-align: center;
    padding: 3.5rem 1rem 2rem 1rem;
    max-width: 650px;
    margin: 0 auto;
}}

.chat-empty-icon {{
    font-size: 2.8rem;
    margin-bottom: 0.75rem;
    display: inline-block;
}}

.chat-empty-title {{
    font-size: 1.75rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 0.4rem;
}}

.chat-empty-subtitle {{
    font-size: 0.95rem;
    color: var(--text-muted);
    line-height: 1.5;
    margin-bottom: 2rem;
}}

/* Thẻ gợi ý câu hỏi dạng Grid 2x2 */
.suggestion-card {{
    background-color: var(--surface-bg);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 12px 14px;
    cursor: pointer;
    text-align: left;
    transition: background-color 0.15s ease, border-color 0.15s ease;
    margin-bottom: 8px;
}}

.suggestion-card:hover {{
    background-color: var(--surface-hover);
    border-color: var(--border-medium);
}}

.suggestion-prompt {{
    font-size: 0.9rem;
    font-weight: 500;
    color: var(--text-primary);
    margin-bottom: 2px;
}}

.suggestion-desc {{
    font-size: 0.78rem;
    color: var(--text-muted);
}}

/* ==========================================================================
   5. BONG BÓNG TIN NHẮN (MESSAGE TURNS CHUẨN CHATGPT)
   ========================================================================== */
[data-testid="stChatMessage"] {{
    background-color: transparent !important;
    padding: 12px 0 !important;
    gap: 12px !important;
}}

/* Lượt người dùng: căn phải với bong bóng kiểu pill */
.user-turn-wrapper {{
    display: flex;
    justify-content: flex-end;
    width: 100%;
}}

.user-turn-body {{
    background-color: var(--user-bubble-bg);
    color: var(--user-bubble-text);
    padding: 10px 16px;
    border-radius: 20px;
    max-width: 80%;
    word-break: break-word;
    font-size: 0.98rem;
    line-height: 1.55;
    border: 1px solid var(--border-subtle);
}}

/* Lượt trợ lý: hiển thị chuẩn phong cách ChatGPT */
.bot-turn-wrapper {{
    display: flex;
    gap: 12px;
    width: 100%;
    align-items: flex-start;
}}

.bot-avatar-icon {{
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background-color: var(--accent);
    color: #FFFFFF;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 15px;
    flex-shrink: 0;
    margin-top: 2px;
}}

.bot-turn-content {{
    flex: 1 1 auto;
    color: var(--text-primary);
    font-size: 0.98rem;
    line-height: 1.65;
    word-break: break-word;
}}

/* Huy hiệu nguồn dữ liệu (Provenance) */
.source-badge {{
    display: inline-block;
    padding: 2px 8px;
    margin-right: 6px;
    margin-bottom: 4px;
    font-size: 0.75rem;
    border-radius: 6px;
    background: var(--source-badge-bg);
    border: 1px solid var(--source-badge-border);
    color: var(--source-badge-text);
    font-weight: 500;
}}

/* ==========================================================================
   6. Ô NHẬP LIỆU ST.CHAT_INPUT CHUẨN CHATGPT & CĂN KHUNG
   ========================================================================== */
[data-testid="stBottom"] {{
    background-color: transparent !important;
}}

[data-testid="stBottom"] > div {{
    max-width: 840px !important;
    margin: 0 auto !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    box-sizing: border-box !important;
}}

[data-testid="stChatInput"] {{
    background-color: var(--chat-input-bg) !important;
    border: 1px solid var(--chat-input-border) !important;
    border-radius: 24px !important;
    padding: 4px 8px !important;
    box-shadow: var(--shadow-chat-input) !important;
    max-width: 840px !important;
    margin: 0 auto !important;
    width: 100% !important;
    box-sizing: border-box !important;
}}

[data-testid="stChatInput"] textarea {{
    color: var(--text-primary) !important;
    font-size: 0.96rem !important;
    background-color: transparent !important;
}}

[data-testid="stChatInput"] textarea::placeholder {{
    color: var(--chat-input-placeholder) !important;
}}

[data-testid="stChatInput"] button {{
    color: var(--text-secondary) !important;
    background-color: transparent !important;
    border-radius: 50% !important;
    transition: background-color 0.15s ease !important;
}}

[data-testid="stChatInput"] button:hover {{
    background-color: var(--surface-hover) !important;
    color: var(--text-primary) !important;
}}

/* Xóa bỏ phần tử chat-bottom-status-line */
.chat-bottom-status-line {{
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
}}

/* Định dạng các nút hành động Ghim và Xóa từng hội thoại trong Sidebar */
div[data-testid="stSidebar"] button[key^="btn_pin_"],
div[data-testid="stSidebar"] button[key^="btn_del_"] {{
    background-color: transparent !important;
    color: var(--text-muted) !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 2px 4px !important;
    font-size: 0.82rem !important;
    min-width: 26px !important;
    height: 30px !important;
    transition: all 0.15s ease !important;
}}

div[data-testid="stSidebar"] button[key^="btn_pin_"]:hover {{
    background-color: var(--surface-hover) !important;
    color: var(--accent) !important;
}}

div[data-testid="stSidebar"] button[key^="btn_del_"]:hover {{
    background-color: var(--danger-bg) !important;
    color: var(--danger-text) !important;
}}

/* Đảm bảo hàng chứa nút hội thoại và 2 nút hành động nằm ngang gọn gàng */
div[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"]:has(button[key^="btn_pin_"]) {{
    align-items: center !important;
    gap: 4px !important;
    margin-bottom: 2px !important;
}}

/* ==========================================================================
   7. CÁC THÀNH PHẦN QUẢN TRỊ, BẢNG BIỂU & FORM
   ========================================================================== */
[data-testid="stVerticalBlockBorderWrapper"] {{
    background-color: var(--sidebar-bg) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 12px !important;
}}

.stTextInput > div > div > input,
.stSelectbox > div > div,
.stTextArea > div > div > textarea {{
    background-color: var(--app-bg) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 8px !important;
}}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {{
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 1px var(--accent) !important;
}}

[data-testid="stDataFrame"] {{
    background-color: var(--sidebar-bg) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 8px !important;
}}

button[data-baseweb="tab"] {{
    color: var(--text-muted) !important;
    background-color: transparent !important;
    font-weight: 500 !important;
}}

button[data-baseweb="tab"][aria-selected="true"] {{
    color: var(--text-primary) !important;
    border-bottom-color: var(--accent) !important;
}}

div[data-testid="stMetricValue"] {{
    color: var(--text-primary) !important;
    font-weight: 600 !important;
}}

div[data-testid="stMetricLabel"] {{
    color: var(--text-muted) !important;
}}

[data-testid="stAlert"] {{
    border-radius: 10px !important;
    padding: 10px 14px !important;
    font-size: 0.92rem !important;
}}

div[data-testid="stAlert"]:has([data-testid="stNotificationContentSuccess"]) {{
    background-color: var(--alert-success-bg) !important;
    border: 1px solid var(--alert-success-border) !important;
    color: var(--alert-success-text) !important;
}}

div[data-testid="stAlert"]:has([data-testid="stNotificationContentInfo"]) {{
    background-color: var(--alert-info-bg) !important;
    border: 1px solid var(--alert-info-border) !important;
    color: var(--alert-info-text) !important;
}}

div[data-testid="stAlert"]:has([data-testid="stNotificationContentWarning"]) {{
    background-color: var(--alert-warning-bg) !important;
    border: 1px solid var(--alert-warning-border) !important;
    color: var(--alert-warning-text) !important;
}}

div[data-testid="stAlert"]:has([data-testid="stNotificationContentError"]) {{
    background-color: var(--alert-error-bg) !important;
    border: 1px solid var(--alert-error-border) !important;
    color: var(--alert-error-text) !important;
}}

[data-testid="stAlert"] p, [data-testid="stAlert"] span {{
    color: inherit !important;
}}

/* ==========================================================================
   8. TỐI ƯU RESPONSIVE MÀN HÌNH NHỎ (< 768px)
   ========================================================================== */
@media (max-width: 768px) {{
    .block-container {{
        padding-left: 0.85rem !important;
        padding-right: 0.85rem !important;
        padding-top: 0.85rem !important;
        padding-bottom: 6.5rem !important;
    }}
    
    .chat-view-title {{
        font-size: 1.05rem !important;
    }}
    
    .user-turn-body {{
        max-width: 90% !important;
    }}
}}
</style>
"""


# Khởi tạo hằng số CUSTOM_CSS mặc định (tự động theo thiết bị / System theme)
CUSTOM_CSS = get_custom_css()
