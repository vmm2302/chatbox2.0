"""Theme và CSS tùy biến giao diện Chatbox 2.0 theo phong cách kết hợp ChatGPT và Gemini.

Hệ thống thiết kế chuẩn hóa:
- Đồng bộ giao diện theo thiết bị (System theme / Light & Dark Theme):
  + Chế độ sáng (Light): Nền chính (#FFFFFF), sidebar (#F7F7F8), bề mặt (#FFFFFF),
    đường viền (#E5E7EB), chữ chính (#171717), chữ phụ (#667085).
  + Chế độ tối (Dark): Nền chính (#212121), sidebar (#171717), bề mặt (#2A2A2A),
    đường viền (#383838), chữ chính (#ECECEC), chữ phụ (#A1A1AA).
  + Màu nhận diện chính: Xanh ngọc (#10A37F).
  + Màu nhấn phụ tiết chế (Gemini-inspired): Xanh tím (#6366F1 / #818CF8) cho thẻ gợi ý,
    điểm nhấn đặc biệt và badge phân cấp.
- Bố cục & trải nghiệm người dùng:
  + Sidebar bên trái: Thương hiệu & New Chat ở đầu, tìm kiếm nhanh,
    lịch sử phân nhóm thời gian và nhóm ghim cuộn độc lập ở giữa,
    khu vực tài khoản ghim cố định sát đáy.
  + Khung hội thoại trung tâm tập trung, giới hạn độ rộng đọc tối ưu 840px.
  + Lượt người dùng: Căn phải, bong bóng bo tròn mềm mại với nền nhẹ.
  + Lượt chatbot: Thoáng đãng, dễ đọc theo chuẩn typography ChatGPT & Gemini, không đóng khung nặng.
  + Chip/Badge nguồn dữ liệu (Provenance) tinh tế, nổi bật nguồn tri thức thực tế.
  + Ô nhập st.chat_input bo tròn 24-26px, căn giữa theo khung chat.
  + Màn hình chào mừng với 4 thẻ gợi ý cân đối (2 cột trên desktop, 1 cột trên mobile).
"""

from typing import Optional


LIGHT_PALETTE = {
    "bg_main": "#FFFFFF",
    "bg_sidebar": "#F7F7F8",
    "bg_surface": "#FFFFFF",
    "bg_hover": "#F0F0F2",
    "border_subtle": "#E5E7EB",
    "border_medium": "#D1D5DB",
    "text_primary": "#171717",
    "text_secondary": "#667085",
    "text_muted": "#9CA3AF",
    "accent": "#10A37F",
    "accent_hover": "#0E906F",
    "accent_secondary": "#6366F1",
    "accent_secondary_hover": "#4F46E5",
    "user_bubble": "#F4F4F6",
    "danger": "#EF4444",
}

DARK_PALETTE = {
    "bg_main": "#212121",
    "bg_sidebar": "#171717",
    "bg_surface": "#2A2A2A",
    "bg_hover": "#323232",
    "border_subtle": "#383838",
    "border_medium": "#444444",
    "text_primary": "#ECECEC",
    "text_secondary": "#A1A1AA",
    "text_muted": "#71717A",
    "accent": "#10A37F",
    "accent_hover": "#0E906F",
    "accent_secondary": "#818CF8",
    "accent_secondary_hover": "#6366F1",
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
            --surface-bg: #2A2A2A !important;
            --surface-hover: #323232 !important;
            --border-subtle: #383838 !important;
            --border-medium: #444444 !important;
            --text-primary: #ECECEC !important;
            --text-secondary: #A1A1AA !important;
            --text-muted: #71717A !important;
            --user-bubble-bg: #2F2F2F !important;
            --user-bubble-text: #ECECEC !important;
            --chat-input-bg: #2A2A2A !important;
            --chat-input-border: #383838 !important;
            --chat-input-placeholder: #71717A !important;
            --popover-bg: #1F1F1F !important;
            --card-bg: #2A2A2A !important;
            --card-border: #383838 !important;
            --active-item-bg: #323232 !important;
            --active-item-text: #FFFFFF !important;
            --source-badge-bg: #132A22 !important;
            --source-badge-border: #1E4638 !important;
            --source-badge-text: #34D399 !important;
            --accent-secondary: #818CF8 !important;
            --accent-secondary-hover: #6366F1 !important;
            --accent-secondary-subtle: #1E1B4B !important;
            --accent-secondary-border: #3730A3 !important;
            --accent-secondary-text: #C7D2FE !important;
            --role-user-bg: #172554 !important;
            --role-user-border: #1E3A8A !important;
            --role-user-text: #60A5FA !important;
            --role-admin-bg: #2E1065 !important;
            --role-admin-border: #4C1D95 !important;
            --role-admin-text: #C084FC !important;
            --code-block-bg: #1A1A1A !important;
            --code-block-border: #383838 !important;
            --danger-bg: #3F1D1D !important;
            --danger-border: #7F1D1D !important;
            --danger-text: #F87171 !important;
            --shadow-popover: 0 10px 25px -5px rgba(0, 0, 0, 0.6) !important;
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
            --sidebar-bg: #F7F7F8 !important;
            --surface-bg: #FFFFFF !important;
            --surface-hover: #F0F0F2 !important;
            --border-subtle: #E5E7EB !important;
            --border-medium: #D1D5DB !important;
            --text-primary: #171717 !important;
            --text-secondary: #667085 !important;
            --text-muted: #9CA3AF !important;
            --user-bubble-bg: #F4F4F6 !important;
            --user-bubble-text: #171717 !important;
            --chat-input-bg: #FFFFFF !important;
            --chat-input-border: #E5E7EB !important;
            --chat-input-placeholder: #9CA3AF !important;
            --popover-bg: #FFFFFF !important;
            --card-bg: #FFFFFF !important;
            --card-border: #E5E7EB !important;
            --active-item-bg: #EAEBF0 !important;
            --active-item-text: #171717 !important;
            --source-badge-bg: #F0FDF4 !important;
            --source-badge-border: #DCFCE7 !important;
            --source-badge-text: #10A37F !important;
            --accent-secondary: #6366F1 !important;
            --accent-secondary-hover: #4F46E5 !important;
            --accent-secondary-subtle: #EEF2FF !important;
            --accent-secondary-border: #C7D2FE !important;
            --accent-secondary-text: #4338CA !important;
            --role-user-bg: #EFF6FF !important;
            --role-user-border: #BFDBFE !important;
            --role-user-text: #1D4ED8 !important;
            --role-admin-bg: #F5F3FF !important;
            --role-admin-border: #DDD6FE !important;
            --role-admin-text: #6D28D9 !important;
            --code-block-bg: #F8FAFC !important;
            --code-block-border: #E2E8F0 !important;
            --danger-bg: #FEF2F2 !important;
            --danger-border: #FECACA !important;
            --danger-text: #DC2626 !important;
            --shadow-popover: 0 10px 25px -5px rgba(0, 0, 0, 0.08) !important;
            --shadow-chat-input: 0 4px 20px -2px rgba(0, 0, 0, 0.06) !important;
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
    /* Điểm nhấn thương hiệu chính: Xanh ngọc (ChatGPT) */
    --accent: #10A37F;
    --accent-hover: #0E906F;
    --accent-subtle: #ECFDF5;
    --accent-border: #A7F3D0;

    /* Điểm nhấn phụ tiết chế: Xanh tím (Gemini inspiration) */
    --accent-secondary: #6366F1;
    --accent-secondary-hover: #4F46E5;
    --accent-secondary-subtle: #EEF2FF;
    --accent-secondary-border: #C7D2FE;
    --accent-secondary-text: #4338CA;

    /* Màu nguy hiểm & Cảnh báo an toàn */
    --danger: #EF4444;
    --danger-hover: #DC2626;
    --danger-bg: #FEF2F2;
    --danger-border: #FECACA;
    --danger-text: #DC2626;

    /* Chuẩn hóa bán kính bo góc */
    --radius-sm: 6px;
    --radius-md: 10px;
    --radius-lg: 12px;
    --radius-pill: 24px;

    /* Theme Sáng (Light - Mặc định theo thiết bị) */
    --app-bg: #FFFFFF;
    --sidebar-bg: #F7F7F8;
    --surface-bg: #FFFFFF;
    --surface-hover: #F0F0F2;
    --border-subtle: #E5E7EB;
    --border-medium: #D1D5DB;
    --text-primary: #171717;
    --text-secondary: #667085;
    --text-muted: #9CA3AF;
    --user-bubble-bg: #F4F4F6;
    --user-bubble-text: #171717;
    --chat-input-bg: #FFFFFF;
    --chat-input-border: #E5E7EB;
    --chat-input-placeholder: #9CA3AF;
    --popover-bg: #FFFFFF;
    --card-bg: #FFFFFF;
    --card-border: #E5E7EB;
    --active-item-bg: #EAEBF0;
    --active-item-text: #171717;
    --source-badge-bg: #F0FDF4;
    --source-badge-border: #DCFCE7;
    --source-badge-text: #10A37F;
    --role-user-bg: #EFF6FF;
    --role-user-border: #BFDBFE;
    --role-user-text: #1D4ED8;
    --role-admin-bg: #F5F3FF;
    --role-admin-border: #DDD6FE;
    --role-admin-text: #6D28D9;
    --code-block-bg: #F8FAFC;
    --code-block-border: #E2E8F0;
    --shadow-popover: 0 10px 25px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.04);
    --shadow-chat-input: 0 4px 20px -2px rgba(0, 0, 0, 0.06);

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
        --surface-bg: #2A2A2A;
        --surface-hover: #323232;
        --border-subtle: #383838;
        --border-medium: #444444;
        --text-primary: #ECECEC;
        --text-secondary: #A1A1AA;
        --text-muted: #71717A;
        --user-bubble-bg: #2F2F2F;
        --user-bubble-text: #ECECEC;
        --chat-input-bg: #2A2A2A;
        --chat-input-border: #383838;
        --chat-input-placeholder: #71717A;
        --popover-bg: #1F1F1F;
        --card-bg: #2A2A2A;
        --card-border: #383838;
        --active-item-bg: #323232;
        --active-item-text: #FFFFFF;
        --source-badge-bg: #132A22;
        --source-badge-border: #1E4638;
        --source-badge-text: #34D399;
        --accent-secondary: #818CF8;
        --accent-secondary-hover: #6366F1;
        --accent-secondary-subtle: #1E1B4B;
        --accent-secondary-border: #3730A3;
        --accent-secondary-text: #C7D2FE;
        --role-user-bg: #172554;
        --role-user-border: #1E3A8A;
        --role-user-text: #60A5FA;
        --role-admin-bg: #2E1065;
        --role-admin-border: #4C1D95;
        --role-admin-text: #C084FC;
        --code-block-bg: #1A1A1A;
        --code-block-border: #383838;
        --danger-bg: #3F1D1D;
        --danger-border: #7F1D1D;
        --danger-text: #F87171;
        --shadow-popover: 0 10px 25px -5px rgba(0, 0, 0, 0.6);
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

/* Áp dụng nền và typography chuẩn hóa cho ứng dụng */
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
    letter-spacing: -0.015em !important;
}}

/* Giới hạn độ rộng vùng đọc trung tâm chuẩn ChatGPT & Gemini (840px) */
.block-container {{
    max-width: 840px !important;
    width: 100% !important;
    padding-top: 1.25rem !important;
    padding-bottom: 7rem !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    margin: 0 auto !important;
    box-sizing: border-box !important;
}}

/* Ẩn các nút deploy/status của Streamlit nhưng LUÔN GIỮ nút thu gọn & mở sidebar */
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

/* Nút thu gọn & mở lại sidebar luôn hiển thị rõ ràng, dễ nhận biết và hoạt động tốt */
[data-testid="stSidebarCollapsedControl"],
[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapseButton"] {{
    visibility: visible !important;
    display: flex !important;
    opacity: 1 !important;
    color: var(--text-secondary) !important;
    transition: color 0.15s ease, background-color 0.15s ease !important;
}}

[data-testid="stSidebarCollapsedControl"]:hover,
[data-testid="stExpandSidebarButton"]:hover,
[data-testid="stSidebarCollapseButton"]:hover {{
    color: var(--text-primary) !important;
    background-color: var(--surface-hover) !important;
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
    padding: 0.85rem 0.75rem 0.4rem 0.75rem !important;
}}

.sidebar-header-box {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 4px 6px 12px 6px;
}}

.sidebar-app-icon {{
    font-size: 1.4rem;
    line-height: 1;
}}

.sidebar-brand-text {{
    display: flex;
    align-items: baseline;
    gap: 6px;
}}

.sidebar-app-title {{
    font-size: 1.12rem;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: -0.015em;
}}

.sidebar-app-badge {{
    font-size: 0.68rem;
    font-weight: 600;
    padding: 1px 6px;
    border-radius: 9999px;
    background: var(--surface-bg);
    color: var(--text-muted);
    border: 1px solid var(--border-subtle);
}}

/* Nút tạo cuộc trò chuyện mới (+ Đoạn chat mới) */
.stButton > button[key="btn_sidebar_new_chat"] {{
    background-color: var(--surface-bg) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: var(--radius-md) !important;
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
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
}}

.stButton > button[key="btn_sidebar_new_chat"]:hover {{
    background-color: var(--surface-hover) !important;
    border-color: var(--border-medium) !important;
    color: var(--accent) !important;
}}

/* Ô tìm kiếm hội thoại trong sidebar */
section[data-testid="stSidebar"] div[class*="st-key-sidebar_top"] .stTextInput input {{
    background-color: var(--surface-bg) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: var(--radius-sm) !important;
    font-size: 0.86rem !important;
    padding: 6px 10px !important;
    color: var(--text-primary) !important;
}}

section[data-testid="stSidebar"] div[class*="st-key-sidebar_top"] .stTextInput input:focus {{
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 1px var(--accent) !important;
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
    letter-spacing: 0.05em;
    padding: 10px 6px 4px 6px;
    margin-top: 4px;
}}

/* Nút từng cuộc trò chuyện trong lịch sử */
div[data-testid="stSidebar"] div.stButton > button[key^="btn_conv_"] {{
    background-color: transparent !important;
    color: var(--text-secondary) !important;
    border: 1px solid transparent !important;
    border-radius: var(--radius-sm) !important;
    padding: 7px 10px !important;
    font-size: 0.88rem !important;
    font-weight: 400 !important;
    text-align: left !important;
    width: 100% !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    margin-bottom: 2px !important;
    transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease !important;
}}

div[data-testid="stSidebar"] div.stButton > button[key^="btn_conv_"]:hover {{
    background-color: var(--surface-hover) !important;
    color: var(--text-primary) !important;
}}

/* Mục hội thoại đang mở (active) với điểm nhấn xanh ngọc phong cách ChatGPT & Gemini */
div[data-testid="stSidebar"] div.stButton > button[key^="btn_conv_active_"] {{
    background-color: var(--active-item-bg) !important;
    color: var(--active-item-text) !important;
    font-weight: 500 !important;
    border: 1px solid var(--border-subtle) !important;
    border-left: 3px solid var(--accent) !important;
    padding-left: 8px !important;
    border-radius: var(--radius-sm) !important;
}}

/* Định dạng các nút hành động Ghim và Xóa từng hội thoại trong Sidebar */
div[data-testid="stSidebar"] button[key^="btn_pin_"],
div[data-testid="stSidebar"] button[key^="btn_del_"] {{
    background-color: transparent !important;
    color: var(--text-muted) !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    padding: 2px 2px !important;
    font-size: 0.82rem !important;
    min-width: 26px !important;
    height: 30px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    transition: all 0.15s ease !important;
}}

div[data-testid="stSidebar"] button[key^="btn_pin_"]:hover {{
    background-color: var(--surface-hover) !important;
    color: var(--accent-secondary) !important;
}}

div[data-testid="stSidebar"] button[key^="btn_del_"]:hover {{
    background-color: var(--danger-bg) !important;
    color: var(--danger-text) !important;
}}

div[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"]:has(button[key^="btn_pin_"]) {{
    align-items: center !important;
    gap: 3px !important;
    margin-bottom: 2px !important;
}}

/* 3.3. KHU VỰC TÀI KHOẢN Ở ĐÁY SIDEBAR (st-key-sidebar_footer) - GHIM SÁT ĐÁY KHÔNG ĐÈ */
section[data-testid="stSidebar"] div[data-testid="stLayoutWrapper"]:has(div[class*="st-key-sidebar_footer"]),
section[data-testid="stSidebar"] div[class*="st-key-sidebar_footer"] {{
    flex: 0 0 auto !important;
    margin-top: auto !important;
    height: auto !important;
    position: relative !important;
}}

section[data-testid="stSidebar"] div[class*="st-key-sidebar_footer"] {{
    padding: 0.65rem 0.65rem 0.75rem 0.65rem !important;
    border-top: 1px solid var(--border-subtle) !important;
    background-color: var(--sidebar-bg) !important;
}}

/* Nút popover tài khoản ở chân sidebar */
[data-testid="stSidebar"] [data-testid="stPopover"] button,
[data-testid="stSidebar"] button[data-testid="stPopoverButton"] {{
    background-color: var(--surface-bg) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: var(--radius-md) !important;
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
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02) !important;
}}

[data-testid="stSidebar"] [data-testid="stPopover"] button:hover,
[data-testid="stSidebar"] button[data-testid="stPopoverButton"]:hover {{
    background-color: var(--surface-hover) !important;
    border-color: var(--border-medium) !important;
}}

/* Hộp popover menu tài khoản */
[data-testid="stPopoverBody"] {{
    background-color: var(--popover-bg) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: var(--radius-lg) !important;
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

/* Nút hành động nguy hiểm (xóa lịch sử, xóa hội thoại) trong Popover */
[data-testid="stPopoverBody"] button[key="btn_popover_del_curr"]:hover,
[data-testid="stPopoverBody"] button[key="btn_popover_clear_all"]:hover {{
    background-color: var(--danger-bg) !important;
    color: var(--danger-text) !important;
    border-color: var(--danger-border) !important;
}}

/* Nút Đăng xuất */
[data-testid="stPopoverBody"] button[key="btn_popover_logout"]:hover {{
    background-color: var(--surface-hover) !important;
    color: var(--text-primary) !important;
}}

/* Badge vai trò hệ thống */
.role-badge-user {{
    display: inline-block;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-weight: 600;
    border-radius: 9999px;
    background: var(--role-user-bg);
    color: var(--role-user-text);
    border: 1px solid var(--role-user-border);
}}

.role-badge-admin {{
    display: inline-block;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-weight: 600;
    border-radius: 9999px;
    background: var(--role-admin-bg);
    color: var(--role-admin-text);
    border: 1px solid var(--role-admin-border);
}}

/* ==========================================================================
   4. KHUNG CHAT CHÍNH: HEADER, MÀN HÌNH CHÀO MỪNG VÀ GỢI Ý
   ========================================================================== */
.chat-top-bar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 4px 0 12px 0;
    margin-bottom: 6px;
    border-bottom: 1px solid var(--border-subtle);
}}

.chat-top-left {{
    display: flex;
    align-items: center;
    gap: 10px;
}}

.chat-view-title {{
    font-size: 1.15rem;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: -0.01em;
}}

.chat-local-pill {{
    font-size: 0.72rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 9999px;
    background: var(--surface-bg);
    color: var(--accent);
    border: 1px solid var(--accent-border);
}}

/* Màn hình chào mừng khi chưa có tin nhắn (Empty State phong cách ChatGPT + Gemini) */
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
    filter: drop-shadow(0 2px 8px rgba(16, 163, 127, 0.2));
}}

.chat-empty-title {{
    font-size: 1.75rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 0.45rem;
    letter-spacing: -0.02em;
}}

.chat-empty-subtitle {{
    font-size: 0.95rem;
    color: var(--text-muted);
    line-height: 1.55;
    margin-bottom: 2rem;
}}

/* Thẻ gợi ý câu hỏi (Suggestion Cards) với điểm nhấn xanh tím nhẹ (Gemini-inspired) */
.stButton > button[key^="sug_card_"] {{
    background-color: var(--surface-bg) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: var(--radius-lg) !important;
    padding: 14px 16px !important;
    cursor: pointer !important;
    text-align: left !important;
    min-height: 84px !important;
    height: auto !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
    align-items: flex-start !important;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    margin-bottom: 8px !important;
    width: 100% !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02) !important;
    color: var(--text-primary) !important;
}}

.stButton > button[key^="sug_card_"]:hover {{
    background-color: var(--surface-hover) !important;
    border-color: var(--accent-secondary) !important;
    box-shadow: 0 4px 16px rgba(99, 102, 241, 0.12) !important;
    transform: translateY(-1px) !important;
}}

.stButton > button[key^="sug_card_"]:active {{
    transform: translateY(0) !important;
}}

/* ==========================================================================
   5. BONG BÓNG TIN NHẮN (MESSAGE TURNS: CHATGPT & GEMINI BLEND)
   ========================================================================== */
[data-testid="stChatMessage"] {{
    background-color: transparent !important;
    padding: 12px 0 !important;
    gap: 12px !important;
}}

/* Lượt người dùng: căn phải với bong bóng bo tròn mềm mại */
.user-turn-wrapper {{
    display: flex;
    justify-content: flex-end;
    align-items: flex-end;
    gap: 8px;
    width: 100%;
}}

.user-turn-author {{
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}}

.user-turn-body {{
    background-color: var(--user-bubble-bg);
    color: var(--user-bubble-text);
    padding: 10px 16px;
    border-radius: 18px 18px 4px 18px;
    max-width: 82%;
    word-break: break-word;
    font-size: 0.98rem;
    line-height: 1.55;
    border: 1px solid var(--border-subtle);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}}

/* Lượt trợ lý: hiển thị thoáng, không đóng khung nặng nề */
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

/* Huy hiệu nguồn dữ liệu (Provenance Chips phong cách Gemini & ChatGPT) */
.source-badge {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    margin-right: 6px;
    margin-bottom: 4px;
    font-size: 0.76rem;
    border-radius: 9999px;
    background: var(--source-badge-bg);
    border: 1px solid var(--source-badge-border);
    color: var(--source-badge-text);
    font-weight: 500;
    line-height: 1.4;
}}

.source-badge-primary {{
    background: var(--accent-subtle);
    border: 1px solid var(--accent-border);
    color: var(--accent);
}}

.source-badge-secondary {{
    background: var(--accent-secondary-subtle);
    border: 1px solid var(--accent-secondary-border);
    color: var(--accent-secondary-text);
}}

/* ==========================================================================
   6. Ô NHẬP LIỆU ST.CHAT_INPUT BO TRÒN 24-26PX VÀ CĂN GIỮA
   ========================================================================== */
[data-testid="stBottom"] {{
    background-color: var(--app-bg) !important;
    border-top: 1px solid var(--border-subtle) !important;
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
    border-radius: 26px !important;
    padding: 4px 8px !important;
    box-shadow: var(--shadow-chat-input) !important;
    max-width: 840px !important;
    margin: 0 auto !important;
    width: 100% !important;
    box-sizing: border-box !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}}

[data-testid="stChatInput"]:focus-within {{
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px rgba(16, 163, 127, 0.2), var(--shadow-chat-input) !important;
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
    transition: all 0.15s ease !important;
}}

[data-testid="stChatInput"] button:hover:not(:disabled) {{
    background-color: var(--accent) !important;
    color: #FFFFFF !important;
}}

[data-testid="stChatInput"] button:disabled {{
    opacity: 0.4 !important;
    cursor: not-allowed !important;
}}

/* ==========================================================================
   7. MÀN HÌNH ĐĂNG NHẬP, ĐĂNG KÝ VÀ THẺ THIẾT LẬP HỆ THỐNG
   ========================================================================== */
.auth-header-box {{
    text-align: center;
    margin-top: 1.5rem;
    margin-bottom: 1.75rem;
}}

.auth-header-icon {{
    font-size: 3rem;
    margin-bottom: 0.5rem;
    filter: drop-shadow(0 2px 8px rgba(16, 163, 127, 0.25));
}}

.auth-header-title {{
    font-size: 1.85rem;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 0.35rem;
    letter-spacing: -0.02em;
}}

.auth-header-desc {{
    color: var(--text-muted);
    font-size: 0.95rem;
    max-width: 500px;
    margin: 0 auto !important;
    text-align: center;
    line-height: 1.5;
}}

/* Thẻ hướng dẫn thiết lập Quản trị viên (Admin Setup Card) thích ứng sáng/tối */
.admin-setup-card {{
    background-color: var(--accent-secondary-subtle);
    border: 1px solid var(--accent-secondary-border);
    border-radius: var(--radius-lg);
    padding: 16px 20px;
    margin-bottom: 1.5rem;
    color: var(--text-primary);
}}

.admin-setup-title {{
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--accent-secondary-text);
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 8px;
}}

.admin-setup-desc {{
    margin: 0 0 10px 0;
    font-size: 0.92rem;
    line-height: 1.55;
    color: var(--text-secondary);
}}

.admin-setup-code {{
    background-color: var(--code-block-bg);
    padding: 10px 14px;
    border-radius: var(--radius-sm);
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.95rem;
    color: var(--accent);
    border: 1px solid var(--border-subtle);
    margin-bottom: 10px;
    user-select: all;
}}

.admin-setup-note {{
    margin: 0;
    font-size: 0.84rem;
    color: var(--text-muted);
}}

/* ==========================================================================
   8. CÁC THÀNH PHẦN QUẢN TRỊ, BẢNG BIỂU & FORM
   ========================================================================== */
[data-testid="stVerticalBlockBorderWrapper"] {{
    background-color: var(--surface-bg) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: var(--radius-lg) !important;
}}

.stTextInput > div > div > input,
.stSelectbox > div > div,
.stTextArea > div > div > textarea {{
    background-color: var(--app-bg) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: var(--radius-sm) !important;
}}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {{
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 1px var(--accent) !important;
}}

/* Bảng dữ liệu: Đảm bảo hiển thị gọn gàng và cho phép cuộn ngang trên màn hình hẹp */
[data-testid="stDataFrame"] {{
    background-color: var(--surface-bg) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: var(--radius-md) !important;
    overflow-x: auto !important;
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

/* Nút bấm Form & Hành động */
button[kind="primary"] {{
    background-color: var(--accent) !important;
    border-color: var(--accent) !important;
    color: #FFFFFF !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 500 !important;
    transition: background-color 0.15s ease !important;
}}

button[kind="primary"]:hover {{
    background-color: var(--accent-hover) !important;
    border-color: var(--accent-hover) !important;
}}

/* Khối số liệu (Metrics) đồng bộ */
div[data-testid="stMetricValue"] {{
    color: var(--text-primary) !important;
    font-weight: 600 !important;
}}

div[data-testid="stMetricLabel"] {{
    color: var(--text-muted) !important;
    font-size: 0.84rem !important;
}}

/* Thẻ thống kê tùy biến trong Diagnostics */
.stat-card-label {{
    color: var(--text-muted);
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 4px;
}}

.stat-card-value {{
    color: var(--text-primary);
    font-size: 1.15rem;
    font-weight: 600;
    margin-bottom: 4px;
}}

.stat-card-caption {{
    color: var(--text-secondary);
    font-size: 0.8rem;
    line-height: 1.4;
}}

/* Thông báo hệ thống (Alerts) thích ứng */
[data-testid="stAlert"] {{
    border-radius: var(--radius-md) !important;
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
   9. TỐI ƯU RESPONSIVE MÀN HÌNH NHỎ (< 768px)
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

    /* Chuyển các thẻ gợi ý sang bố cục 1 cột cân đối trên màn hình hẹp */
    .stButton > button[key^="sug_card_"] {{
        min-height: 72px !important;
        padding: 12px 14px !important;
        margin-bottom: 6px !important;
    }}
}}
</style>
"""


# Khởi tạo hằng số CUSTOM_CSS mặc định (tự động theo thiết bị / System theme)
CUSTOM_CSS = get_custom_css()
