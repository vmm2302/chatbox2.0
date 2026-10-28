"""Streamlit entrypoint for the learner-facing English vocabulary chatbot.

Run from the repository root with:
    streamlit run src/ui/vocabulary_app.py

This UI reuses the existing authentication, ChatEngine, and conversation
repository. It is intentionally a separate entrypoint so the current app and
other tracked files remain untouched.
"""

from __future__ import annotations

import json
import html
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Keep model loading consistent with the existing local-only application.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from src.auth.service import AuthService
from src.chat.engine import get_engine_state, start_engine_warmup
from src.chat.topic_tracker import TopicTracker
from src.data.conversation_repository import ConversationRepository
from src.data.user_repository import User


logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Từ vựng tiếng Anh · Chatbox 2.0",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner=False)
def get_auth_service() -> AuthService:
    return AuthService()


@st.cache_resource(show_spinner=False)
def get_conversation_repository() -> ConversationRepository:
    return ConversationRepository()


def get_chat_engine(timeout: float = 0.15) -> Any:
    """Return the process-wide ChatEngine instance used by the existing app."""
    from src.chat.engine import get_shared_chat_engine

    return get_shared_chat_engine(timeout=timeout)


def _init_session_state() -> None:
    defaults = {
        "auth_user": None,
        "current_conversation_id": None,
        "messages": [],
        "tracker": None,
        "preferred_level": "Tự động",
        "pending_query": None,
        "auth_tab": "login",
        "auth_notice": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _reset_conversation() -> None:
    st.session_state.current_conversation_id = None
    st.session_state.messages = []
    st.session_state.tracker = None
    st.session_state.pending_query = None


def _short_title(text: str, limit: int = 38) -> str:
    clean = " ".join((text or "").split())
    if not clean:
        return "Cuộc trò chuyện mới"
    return clean if len(clean) <= limit else clean[: limit - 1].rstrip() + "…"


def _build_tracker(engine: Any, messages: Iterable[Dict[str, Any]]) -> TopicTracker:
    tracker = TopicTracker(records=getattr(engine, "records", []))
    for message in messages:
        if message.get("role") == "user":
            try:
                tracker.resolve_query(str(message.get("content", "")))
            except Exception:
                logger.debug("Không thể phục hồi ngữ cảnh từ tin nhắn cũ.", exc_info=True)
    return tracker


def _ensure_tracker(engine: Any) -> TopicTracker:
    tracker = st.session_state.get("tracker")
    if tracker is None:
        tracker = _build_tracker(engine, st.session_state.get("messages", []))
        st.session_state.tracker = tracker
    return tracker


def _meta_value(meta: Any, key: str, default: Any = None) -> Any:
    if isinstance(meta, dict):
        return meta.get(key, default)
    return getattr(meta, key, default) if meta is not None else default


def _record_level(meta: Any) -> Optional[str]:
    direct_level = _meta_value(meta, "level")
    if direct_level:
        return str(direct_level)
    candidates = _meta_value(meta, "candidates", []) or []
    if candidates:
        first = candidates[0]
        record = first.get("record") if isinstance(first, dict) else getattr(first, "record", None)
        if isinstance(record, dict):
            value = record.get("level")
        else:
            value = getattr(record, "level", None)
        return str(value) if value else None
    return None


def _render_assistant_message(content: str, meta: Any = None) -> None:
    st.markdown(content)
    _render_assistant_metadata(meta)


def _render_assistant_metadata(meta: Any = None) -> None:
    word = _meta_value(meta, "word")
    level = _record_level(meta)
    source = _meta_value(meta, "source")

    badges: List[str] = []
    if word:
        badges.append(f"<span>📖 Từ: {html.escape(str(word))}</span>")
    if level:
        badges.append(f"<span>🌱 Trình độ: {html.escape(str(level))}</span>")
    if source:
        badges.append(f"<span>📚 Nguồn: {html.escape(str(source))}</span>")
    if badges:
        st.markdown(f"<div class='answer-meta'>{''.join(badges)}</div>", unsafe_allow_html=True)


def _render_styles() -> None:
    """Apply the learner app's bright, playful visual system locally."""
    st.markdown("""
    <style>
      :root {
        color-scheme: light;
        --background-color: #f5f8ff;
        --secondary-background-color: #eef5f7;
        --text-color: #17253b;
        --primary-color: #11a98b;
        --ink: #17253b;
        --muted: #64748b;
        --teal: #11a98b;
        --teal-dark: #087f6a;
        --coral: #ff806e;
        --lilac: #8877f6;
        --line: #e7edf5;
        --paper: #ffffff;
      }
      html, body, [data-testid="stAppViewContainer"] {
        background: #f5f8ff !important;
        color: var(--ink) !important;
      }
      [data-testid="stAppViewContainer"] {
        background-image:
          radial-gradient(ellipse at 8% 2%, rgba(255, 214, 194, .34), transparent 32%),
          radial-gradient(ellipse at 96% 12%, rgba(195, 235, 226, .42), transparent 32%),
          linear-gradient(180deg, #f8faff 0%, #f4f7fd 100%) !important;
      }
      [data-testid="stHeader"] { background: transparent !important; }
      [data-testid="stMain"] { color: var(--ink) !important; }
      .block-container { max-width: 1180px; padding: 1.6rem 2rem 3rem; }
      [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f2fbf8 0%, #f5f6ff 100%) !important;
        border-right: 1px solid rgba(119, 143, 171, .14);
      }
      [data-testid="stSidebar"] > div:first-child { background: transparent !important; }
      [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p,
      [data-testid="stMarkdownContainer"] li, label, .stCaption, [data-testid="stCaptionContainer"] {
        color: var(--ink);
      }
      [data-testid="stCaptionContainer"] { color: var(--muted) !important; }
      [data-testid="stTextInput"] div[data-baseweb="input"] {
        background: #fff !important; border: 1px solid #dce5ef !important;
        border-radius: 14px !important; box-shadow: none !important;
      }
      [data-testid="stTextInput"] [data-baseweb="input"] > div,
      [data-testid="stTextInput"] [data-baseweb="input"] > div > div {
        background: #fff !important; border-color: #dce5ef !important;
        border-radius: 14px !important; box-shadow: none !important;
      }
      div[data-baseweb="input"] > div {
        background: #fff !important; border: 1px solid #dce5ef !important;
        border-radius: 14px !important; box-shadow: none !important; outline: none !important;
      }
      div[data-baseweb="input"] > div:focus-within {
        border-color: var(--teal) !important; box-shadow: 0 0 0 3px rgba(17, 169, 139, .13) !important;
      }
      div[data-baseweb="input"] > div > input {
        background: #fff !important; color: var(--ink) !important;
        border: 0 !important; box-shadow: none !important; outline: none !important;
      }
      div[data-baseweb="base-input"] {
        background: #fff !important; border: 1px solid #dce5ef !important;
        border-radius: 14px !important; box-shadow: none !important; outline: none !important;
      }
      div[data-baseweb="base-input"]:focus-within {
        border-color: var(--teal) !important; box-shadow: 0 0 0 3px rgba(17, 169, 139, .13) !important;
      }
      div[data-baseweb="base-input"] input {
        background: #fff !important; color: var(--ink) !important;
        border: 0 !important; box-shadow: none !important; outline: none !important;
      }
      [data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
        border-color: var(--teal) !important; box-shadow: 0 0 0 3px rgba(17, 169, 139, .13) !important;
      }
      [data-testid="stTextInput"] input {
        background: #fff !important; color: var(--ink) !important;
        border: 1px solid #dce5ef !important; border-radius: 13px !important;
        box-shadow: none !important;
      }
      [data-testid="stTextInput"] input::placeholder { color: #8795a6 !important; opacity: 1 !important; }
      [data-testid="stTextInput"] div:has(> input) {
        background: #fff !important; border: 1px solid #dce5ef !important;
        border-radius: 13px !important; box-shadow: none !important; outline: none !important;
      }
      [data-testid="stTextInput"] div:has(> input):focus-within {
        border-color: #11a98b !important; box-shadow: 0 0 0 3px rgba(17,169,139,.13) !important;
      }
      [data-testid="stTextInput"] div:has(> input) > input {
        background: transparent !important; border: 0 !important; outline: none !important; box-shadow: none !important;
      }
      input[type="text"], input[type="password"] {
        background-color: #fff !important; color: #17253b !important;
        border: 1px solid #dce5ef !important; border-radius: 13px !important;
        outline: none !important; box-shadow: none !important;
      }
      input[type="text"]:focus, input[type="password"]:focus {
        border-color: #11a98b !important; box-shadow: 0 0 0 3px rgba(17,169,139,.13) !important;
      }
      input[type="text"]::placeholder, input[type="password"]::placeholder { color: #8795a6 !important; opacity: 1 !important; }
      [data-testid="stTextInput"] button {
        background: transparent !important; color: #718197 !important;
        border: 0 !important; box-shadow: none !important;
      }
      [data-testid="stSelectbox"] div[data-baseweb="select"], [data-testid="stChatInput"] textarea {
        background: #fff !important; color: var(--ink) !important;
        border-color: #dce5ef !important; border-radius: 14px !important;
      }
      [data-testid="stTextInput"] input:focus, [data-testid="stChatInput"] textarea:focus {
        border-color: var(--teal) !important; box-shadow: 0 0 0 3px rgba(17, 169, 139, .13) !important;
      }
      button[kind="primary"], [data-testid="stFormSubmitButton"] button {
        background: linear-gradient(135deg, #12b496 0%, #0d9b83 100%) !important;
        border: 0 !important; border-radius: 14px !important; color: white !important;
        font-weight: 700 !important; min-height: 2.8rem;
        box-shadow: 0 8px 18px rgba(17, 169, 139, .18);
        transition: transform .16s ease, box-shadow .16s ease;
      }
      button[kind="primary"]:hover, [data-testid="stFormSubmitButton"] button:hover {
        transform: translateY(-1px); box-shadow: 0 11px 22px rgba(17, 169, 139, .25);
      }
      [data-testid="stBaseButton-secondary"] button, button[kind="secondary"] {
        border-radius: 13px !important; border-color: #dce5ef !important;
        background: rgba(255,255,255,.78) !important; color: var(--ink) !important;
        transition: transform .16s ease, border-color .16s ease, box-shadow .16s ease;
      }
      [data-testid="stBaseButton-secondary"] button:hover, button[kind="secondary"]:hover {
        border-color: rgba(17,169,139,.45) !important; transform: translateY(-1px);
        box-shadow: 0 7px 18px rgba(33, 54, 82, .07);
      }
      [data-testid="stVerticalBlockBorderWrapper"] {
        border-color: rgba(194, 207, 222, .7) !important; border-radius: 22px !important;
        background: rgba(255,255,255,.8);
      }
      [data-testid="stChatMessage"] {
        max-width: 840px; margin: .75rem auto; padding: 1.05rem 1.25rem;
        border: 1px solid rgba(220, 229, 239, .85); border-radius: 22px;
        background: rgba(255,255,255,.84); box-shadow: 0 7px 22px rgba(31, 54, 87, .045);
      }
      [data-testid="stChatInput"] { max-width: 840px; margin: 1rem auto 0; }
      [data-testid="stChatInput"] textarea { border-radius: 22px !important; min-height: 56px; }
      [data-testid="stTabs"] [role="tab"] { border-radius: 12px 12px 0 0; font-weight: 700; }
      [data-testid="stTabs"] [aria-selected="true"] { color: var(--teal-dark) !important; }
      [data-testid="stAlert"] { border-radius: 15px !important; }
      .auth-layout { max-width: 1050px; margin: 3vh auto 1rem; }
      .auth-hero {
        min-height: 450px; padding: 2.4rem 2.2rem; overflow: hidden; position: relative;
        border-radius: 30px; color: #163149;
        background: linear-gradient(145deg, #d9f6ed 0%, #e9f4ff 52%, #f2eaff 100%);
        box-shadow: 0 22px 55px rgba(60, 93, 132, .12);
      }
      .auth-hero:after {
        content: ""; position: absolute; width: 245px; height: 245px; right: -74px; bottom: -95px;
        border-radius: 50%; background: rgba(255,128,110,.22);
      }
      .auth-mark { font-size: 3rem; line-height: 1; margin-bottom: 1.4rem; }
      .auth-overline, .vocab-kicker { color: #07836e; font-size: .72rem; font-weight: 850; letter-spacing: .14em; }
      .auth-hero h1 { color: #183149; font-size: clamp(2rem, 3.5vw, 3.15rem); line-height: 1.08; letter-spacing: -.045em; margin: .7rem 0 1rem; }
      .auth-hero p { color: #4d647a; font-size: 1rem; line-height: 1.7; max-width: 380px; }
      .auth-badges { display: flex; flex-wrap: wrap; gap: .55rem; margin-top: 1.4rem; }
      .auth-badges span { padding: .45rem .7rem; border-radius: 999px; background: rgba(255,255,255,.68); border: 1px solid rgba(255,255,255,.9); font-size: .8rem; font-weight: 750; color: #405970; }
      .auth-form-heading { margin-bottom: .5rem; }
      .auth-form-heading h2 { margin: .2rem 0 .35rem; font-size: 1.55rem; letter-spacing: -.025em; }
      .auth-form-heading p { color: #697b8f; margin: 0 0 1rem; }
      .vocab-header { max-width: 840px; margin: 0 auto .85rem; display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
      .vocab-header h2 { margin: .18rem 0 0; font-size: 1.5rem; letter-spacing: -.025em; }
      .local-pill { border: 1px solid rgba(17,169,139,.25); color: #087f6a; background: rgba(255,255,255,.72); border-radius: 999px; padding: .42rem .75rem; font-size: .78rem; font-weight: 750; white-space: nowrap; }
      .level-track { max-width: 840px; display: grid; grid-template-columns: repeat(4, 1fr); gap: .55rem; margin: .7rem auto 1.1rem; }
      .level-step { padding: .7rem .8rem; border: 1px solid #e3eaf3; border-radius: 15px; background: rgba(255,255,255,.8); color: #718197; font-size: .8rem; font-weight: 800; text-align: center; }
      .level-step.active { border-color: rgba(17,169,139,.4); color: #087f6a; background: linear-gradient(135deg, #dff8ef, #effaff); box-shadow: 0 6px 16px rgba(17,169,139,.09); }
      .vocab-welcome { max-width: 840px; margin: 4vh auto 1.25rem; padding: 2rem 2rem 1.7rem; position: relative; overflow: hidden; border-radius: 28px; background: linear-gradient(120deg, #e3faf2 0%, #e9f4ff 63%, #f6edff 100%); border: 1px solid rgba(255,255,255,.9); box-shadow: 0 15px 40px rgba(54, 93, 133, .09); }
      .vocab-welcome:after { content: "✦"; position: absolute; right: 7%; top: 10%; font-size: 4rem; color: rgba(136,119,246,.26); transform: rotate(14deg); }
      .vocab-welcome h1 { max-width: 620px; color: #19364c; font-size: clamp(1.8rem, 3.2vw, 2.8rem); line-height: 1.12; letter-spacing: -.045em; margin: .4rem 0 .65rem; }
      .vocab-welcome p { max-width: 620px; color: #526a7c; line-height: 1.65; margin: 0; }
      .vocab-eyebrow { color: #07836e; font-size: .72rem; font-weight: 850; letter-spacing: .14em; }
      .level-caption { max-width: 840px; margin: 0 auto .5rem; color: #6c7f91; font-size: .84rem; }
      .suggestion-card { min-height: 88px; padding: 1rem 1.05rem; border: 1px solid #e5ebf4; border-radius: 19px; background: rgba(255,255,255,.9); box-shadow: 0 7px 19px rgba(37,58,87,.045); }
      .suggestion-icon { display: inline-flex; width: 34px; height: 34px; border-radius: 11px; align-items: center; justify-content: center; background: #e1f7f0; margin-right: .55rem; }
      .suggestion-title { display: inline; color: #223b50; font-weight: 800; }
      .suggestion-subtitle { color: #708196; font-size: .83rem; margin: .4rem 0 0 2.9rem; }
      .answer-meta { display: flex; flex-wrap: wrap; gap: .4rem; margin-top: .9rem; }
      .answer-meta span { color: #547083; background: #f2f8fb; border: 1px solid #e1edf1; border-radius: 999px; padding: .3rem .58rem; font-size: .72rem; font-weight: 650; }
      .auth-footnote { color: #738397; font-size: .78rem; margin-top: .9rem; text-align: center; }
      .history-heading { color: #517064; font-size: .72rem; font-weight: 850; letter-spacing: .13em; text-transform: uppercase; margin: 1rem 0 .35rem; }
      .history-active button { border-color: rgba(17,169,139,.5) !important; background: #e4f8f1 !important; }
      @media (max-width: 760px) {
        .block-container { padding: 1rem .8rem 2rem; }
        .auth-layout { margin: .5rem auto; }
        .auth-hero { min-height: 0; padding: 1.5rem; border-radius: 23px; }
        .auth-hero h1 { font-size: 2rem; }
        .vocab-welcome { padding: 1.45rem; margin-top: 1rem; border-radius: 23px; }
        .vocab-header { align-items: flex-start; }
        .level-track { grid-template-columns: repeat(2, 1fr); }
        .local-pill { font-size: .68rem; }
        [data-testid="stChatMessage"] { padding: .9rem; border-radius: 18px; }
      }
    </style>
    """, unsafe_allow_html=True)


def _render_auth_page(auth_service: AuthService) -> None:
    """Custom login/register surface backed by the existing AuthService."""
    init_status, init_error = auth_service.get_system_init_status()
    lifecycle_state, lifecycle = auth_service.get_account_lifecycle_state()

    st.markdown("<div class='auth-layout'>", unsafe_allow_html=True)
    hero_col, form_col = st.columns([1.08, .92], gap="large", vertical_alignment="center")
    with hero_col:
        st.markdown(
            "<section class='auth-hero'>"
            "<div class='auth-mark'>📚</div>"
            "<div class='auth-overline'>HỌC TIẾNG ANH MỖI NGÀY</div>"
            "<h1>Mỗi từ mới,<br>một bước tiến gần hơn.</h1>"
            "<p>Tra cứu từ vựng tiếng Anh theo trình độ A1–B2, khám phá cách dùng và luyện tập qua hội thoại.</p>"
            "<div class='auth-badges'><span>🌱 A1 · Nền tảng</span><span>🚀 B1–B2 · Bứt phá</span><span>🔒 Xử lý cục bộ</span></div>"
            "</section>",
            unsafe_allow_html=True,
        )
    with form_col:
        with st.container(border=True):
            st.markdown(
                "<div class='auth-form-heading'><div class='auth-overline'>CHATBOX 2.0</div>"
                "<h2>Chào mừng bạn 👋</h2><p>Đăng nhập để tiếp tục hành trình học từ vựng.</p></div>",
                unsafe_allow_html=True,
            )
            if init_status == "DB_ERROR":
                st.error("Không thể kết nối cơ sở dữ liệu tài khoản.")
                if init_error:
                    st.caption(str(init_error))
                return
            if init_status == "NO_ADMIN":
                if lifecycle_state == "STATE_2_DB_EMPTY":
                    st.info("Tài khoản quản trị đầu tiên cần được khởi tạo trước khi mở đăng nhập và đăng ký.")
                else:
                    st.info("Hệ thống hiện chưa có quản trị viên đang hoạt động.")
                st.markdown("Chạy lệnh sau trong PowerShell tại thư mục dự án:")
                st.code("python scripts/create_admin.py", language="powershell")
                if st.button("Kiểm tra lại", use_container_width=True):
                    st.rerun()
                return

            if lifecycle_state == "STATE_7_DB_ERROR":
                st.error(str(lifecycle.get("error", "Cơ sở dữ liệu đang gặp lỗi.")))
                return

            selected_tab = "📝 Tạo tài khoản" if st.session_state.get("auth_tab") == "register" else "🔐 Đăng nhập"
            try:
                login_tab, register_tab = st.tabs(["🔐 Đăng nhập", "📝 Tạo tài khoản"], default=selected_tab)
            except TypeError:
                login_tab, register_tab = st.tabs(["🔐 Đăng nhập", "📝 Tạo tài khoản"])

            notice = st.session_state.pop("auth_notice", None)
            if notice:
                st.success(notice)

            with login_tab:
                st.caption("Nhập thông tin tài khoản của bạn.")
                with st.form("vocab_login_form", clear_on_submit=False):
                    username = st.text_input("Tên đăng nhập", placeholder="ví dụ: nguyenvana", key="vocab_login_username").strip()
                    password = st.text_input("Mật khẩu", type="password", placeholder="Nhập mật khẩu", key="vocab_login_password")
                    submitted = st.form_submit_button("Đăng nhập và học thôi", use_container_width=True, type="primary")
                if submitted:
                    success, user, message = auth_service.authenticate(username, password)
                    if success and user:
                        st.session_state.auth_user = user
                        st.session_state.messages = []
                        st.session_state.current_conversation_id = None
                        st.session_state.tracker = None
                        st.session_state.auth_tab = "login"
                        st.rerun()
                    else:
                        st.error(message)

            with register_tab:
                st.caption("Tạo tài khoản người dùng để lưu lịch sử học tập.")
                with st.form("vocab_register_form", clear_on_submit=False):
                    reg_username = st.text_input("Tên đăng nhập *", placeholder="3–30 ký tự", key="vocab_reg_username").strip()
                    display_name = st.text_input("Tên hiển thị", placeholder="Ví dụ: Minh Anh", key="vocab_reg_display_name").strip()
                    reg_password = st.text_input("Mật khẩu *", type="password", placeholder="Tối thiểu 6 ký tự", key="vocab_reg_password")
                    confirm_password = st.text_input("Xác nhận mật khẩu *", type="password", placeholder="Nhập lại mật khẩu", key="vocab_reg_confirm")
                    registered = st.form_submit_button("Tạo tài khoản", use_container_width=True, type="primary")
                if registered:
                    success, _new_user, message = auth_service.register_user(
                        username=reg_username,
                        password=reg_password,
                        confirm_password=confirm_password,
                        display_name=display_name,
                        require_admin_exists=True,
                    )
                    if success:
                        st.session_state.auth_tab = "login"
                        st.session_state.auth_notice = message
                        st.rerun()
                    else:
                        st.error(message)

            st.markdown("<div class='auth-footnote'>🔐 Mật khẩu được bảo vệ bởi hệ thống tài khoản Chatbox.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _load_conversation(
    user: User,
    conversation_id: str,
    repository: ConversationRepository,
    engine: Optional[Any],
) -> bool:
    conversation = repository.get_conversation(user.id, conversation_id)
    if conversation is None:
        st.warning("Không tìm thấy cuộc trò chuyện này trong tài khoản của bạn.")
        return False

    stored_messages = repository.get_messages(user.id, conversation_id)
    messages: List[Dict[str, Any]] = []
    for item in stored_messages:
        messages.append({
            "role": item.role,
            "content": item.content,
            "meta": item.get_meta(),
        })

    st.session_state.current_conversation_id = conversation_id
    st.session_state.messages = messages
    st.session_state.tracker = _build_tracker(engine, messages) if engine is not None else None
    return True


def _render_sidebar(
    user: User,
    auth_service: AuthService,
    repository: ConversationRepository,
    engine: Optional[Any],
) -> None:
    with st.sidebar:
        st.markdown(
            "<div style='display:flex;align-items:center;gap:.65rem;margin:.2rem 0 .8rem;'>"
            "<span style='font-size:1.7rem'>📚</span><div><b style='font-size:1.02rem'>Từ vựng vui</b>"
            "<div style='font-size:.72rem;color:#648075'>CHATBOX 2.0 · A1–B2</div></div></div>",
            unsafe_allow_html=True,
        )

        if st.button("＋ Cuộc trò chuyện mới", use_container_width=True, type="primary"):
            _reset_conversation()
            st.rerun()

        st.selectbox(
            "Trình độ muốn ưu tiên",
            ["Tự động", "A1", "A2", "B1", "B2"],
            key="preferred_level",
            help=(
                "Khi chọn A1–B2, cấp độ sẽ được gửi kèm câu hỏi như một ưu tiên. "
                "Kết quả vẫn dựa trên dữ liệu và bộ truy xuất hiện có."
            ),
        )
        st.caption("Chọn ‘Tự động’ để chatbot tự dùng dữ liệu phù hợp.")
        st.divider()

        st.markdown("<div class='history-heading'>Cuộc trò chuyện</div>", unsafe_allow_html=True)
        try:
            conversations = repository.list_conversations(user.id, limit=30)
        except Exception:
            conversations = []
            logger.exception("Không thể tải lịch sử hội thoại.")
            st.caption("Chưa thể tải lịch sử lúc này.")

        visible_conversations = [c for c in conversations if c.message_count > 0]
        if not visible_conversations:
            st.caption("Các cuộc trò chuyện đã lưu sẽ xuất hiện ở đây.")
        else:
            for conversation in visible_conversations:
                is_active = conversation.id == st.session_state.current_conversation_id
                label = ("● " if is_active else "") + _short_title(conversation.title, 30)
                if st.button(
                    label,
                    key=f"history_{conversation.id}",
                    use_container_width=True,
                    help=conversation.title,
                ):
                    if _load_conversation(user, conversation.id, repository, engine):
                        st.rerun()

        st.divider()
        st.caption(f"Đăng nhập: **{user.display_name}**")
        if st.button("Đăng xuất", use_container_width=True):
            auth_service.logout(user)
            st.session_state.auth_user = None
            _reset_conversation()
            st.rerun()


def _create_conversation_if_needed(
    user: User,
    repository: ConversationRepository,
    query: str,
) -> Optional[str]:
    conversation_id = st.session_state.get("current_conversation_id")
    if conversation_id:
        return conversation_id
    try:
        conversation = repository.create_conversation(user.id, _short_title(query))
        st.session_state.current_conversation_id = conversation.id
        return conversation.id
    except Exception:
        logger.exception("Không thể tạo cuộc trò chuyện mới.")
        st.warning("Không thể lưu hội thoại vào lịch sử, nhưng bạn vẫn có thể tiếp tục tra cứu.")
        return None


def _serialize_meta(meta: Any) -> Optional[str]:
    if meta is None:
        return None
    payload = {
        "mode": _meta_value(meta, "mode"),
        "intent": _meta_value(meta, "intent"),
        "record_id": _meta_value(meta, "record_id"),
        "rrf_score": _meta_value(meta, "rrf_score", 0.0),
        "latency_ms": _meta_value(meta, "latency_ms", 0.0),
        "word": _meta_value(meta, "word"),
        "level": _record_level(meta),
        "source": _meta_value(meta, "source"),
    }
    try:
        return json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError):
        return None


def _effective_query(query: str) -> str:
    level = st.session_state.get("preferred_level", "Tự động")
    if level not in {"A1", "A2", "B1", "B2"}:
        return query
    return f"{query}\n\nƯu tiên thông tin từ trình độ {level}."


def _submit_query(
    query: str,
    user: User,
    engine: Any,
    repository: ConversationRepository,
) -> None:
    clean_query = (query or "").strip()
    if not clean_query:
        return

    conversation_id = _create_conversation_if_needed(user, repository, clean_query)
    try:
        if conversation_id:
            repository.add_message(user.id, conversation_id, "user", clean_query)
    except Exception:
        logger.exception("Không thể lưu câu hỏi vào lịch sử.")

    st.session_state.messages.append({"role": "user", "content": clean_query, "meta": None})
    tracker = _ensure_tracker(engine)

    with st.chat_message("user"):
        st.markdown(clean_query)
        level = st.session_state.get("preferred_level", "Tự động")
        if level != "Tự động":
            st.caption(f"Ưu tiên trình độ {level}")

    answer = ""
    response_meta = None
    with st.chat_message("assistant", avatar="📚"):
        try:
            def response_stream():
                nonlocal response_meta
                for token, meta in engine.ask_stream(_effective_query(clean_query), tracker=tracker):
                    if meta is not None:
                        response_meta = meta
                    if token:
                        yield token

            answer = st.write_stream(response_stream())
            if not isinstance(answer, str):
                answer = str(answer or "")
            if response_meta is not None:
                # The engine's final metadata answer is authoritative if available.
                answer = _meta_value(response_meta, "answer", None) or answer
            if not answer:
                answer = "Mình chưa tìm thấy câu trả lời phù hợp."
                st.markdown(answer)
            _render_assistant_metadata(response_meta)
        except Exception:
            logger.exception("Lỗi khi xử lý câu hỏi bằng ChatEngine.")
            answer = "Xin lỗi, chatbot gặp lỗi khi xử lý câu hỏi. Bạn hãy thử lại sau ít phút."
            st.error(answer)

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "meta": response_meta,
    })

    if conversation_id:
        try:
            repository.add_message(
                user.id,
                conversation_id,
                "assistant",
                answer,
                _serialize_meta(response_meta),
            )
            conversation = repository.get_conversation(user.id, conversation_id)
            if conversation and conversation.title == "Cuộc trò chuyện mới":
                repository.update_title(user.id, conversation_id, _short_title(clean_query))
        except Exception:
            logger.exception("Không thể lưu câu trả lời vào lịch sử.")


def _render_welcome(engine_ready: bool) -> Optional[str]:
    st.markdown(
        "<div class='vocab-welcome'><div class='vocab-eyebrow'>✨ ENGLISH VOCABULARY · A1–B2</div>"
        "<h1>Mỗi câu hỏi nhỏ,<br>thêm một từ mới.</h1>"
        "<p>Khám phá nghĩa, phát âm và cách dùng từ tiếng Anh qua những ví dụ dễ hiểu bằng tiếng Việt.</p></div>",
        unsafe_allow_html=True,
    )
    suggestions = [
        ("📖", "Tra nghĩa từ mới", "generous nghĩa là gì?", "Hiểu nghĩa và cách dùng của một từ."),
        ("✍️", "Học qua ví dụ", "Cho ví dụ với từ improve", "Xem từ mới trong câu tiếng Anh."),
        ("🔎", "Phân biệt từ", "Phân biệt borrow và lend", "Nhận biết những từ dễ nhầm lẫn."),
        ("🌱", "Khám phá A1", "Cho mình danh sách từ vựng trình độ A1", "Bắt đầu với nhóm từ nền tảng."),
    ]
    columns = st.columns(2)
    for index, (icon, title, query, subtitle) in enumerate(suggestions):
        with columns[index % 2]:
            with st.container(border=True):
                st.markdown(
                    f"<div><span class='suggestion-icon'>{icon}</span><span class='suggestion-title'>{title}</span>"
                    f"<div class='suggestion-subtitle'>{subtitle}</div></div>",
                    unsafe_allow_html=True,
                )
                if st.button("Thử câu hỏi này  ↗", key=f"suggestion_{index}", use_container_width=True, disabled=not engine_ready):
                    return query
    return None


def _render_chat(user: User, engine: Any, repository: ConversationRepository) -> None:
    st.markdown(
        "<div class='vocab-header'><div><span class='vocab-kicker'>TRỢ LÝ TỪ VỰNG</span>"
        "<h2>Cùng học từ mới nhé!</h2></div><span class='local-pill'>● Chatbot sẵn sàng</span></div>",
        unsafe_allow_html=True,
    )
    preferred_level = st.session_state.get("preferred_level", "Tự động")
    level_description = "Tự động" if preferred_level == "Tự động" else f"Ưu tiên {preferred_level}"
    st.markdown(f"<div class='level-caption'>Trình độ đang chọn: <b>{html.escape(level_description)}</b></div>", unsafe_allow_html=True)
    level_steps = []
    level_emoji = {"A1": "🌱", "A2": "🌿", "B1": "🚀", "B2": "🌟"}
    for level in ("A1", "A2", "B1", "B2"):
        active_class = " active" if preferred_level == level else ""
        level_steps.append(f"<div class='level-step{active_class}'>{level_emoji[level]} &nbsp;{level}</div>")
    st.markdown(f"<div class='level-track'>{''.join(level_steps)}</div>", unsafe_allow_html=True)

    messages = st.session_state.get("messages", [])
    if not messages:
        pending = _render_welcome(engine_ready=True)
        if pending:
            _submit_query(pending, user, engine, repository)
            st.rerun()
    else:
        for item in messages:
            role = item.get("role", "assistant")
            with st.chat_message(role, avatar="📚" if role == "assistant" else None):
                if role == "assistant":
                    _render_assistant_message(str(item.get("content", "")), item.get("meta"))
                else:
                    st.markdown(str(item.get("content", "")))

    query = st.chat_input("Nhập từ hoặc hỏi về cách dùng từ…")
    if query:
        _submit_query(query, user, engine, repository)
        st.rerun()


def main() -> None:
    _init_session_state()
    _render_styles()

    auth_service = get_auth_service()
    repository = get_conversation_repository()
    user: Optional[User] = st.session_state.get("auth_user")

    if user is not None:
        user = auth_service.verify_active_session(user.id)
        if user is None:
            st.session_state.auth_user = None
            _reset_conversation()
            st.warning("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.")
            st.rerun()
        st.session_state.auth_user = user

    if user is None:
        _render_auth_page(auth_service)
        try:
            start_engine_warmup()
        except Exception:
            logger.exception("Không thể khởi động ChatEngine nền.")
        return

    engine = None
    state, engine_error = get_engine_state()
    if state == "NOT_STARTED":
        try:
            start_engine_warmup()
            state, engine_error = get_engine_state()
        except Exception as exc:
            state, engine_error = "ERROR", str(exc)
    elif state == "READY":
        try:
            engine = get_chat_engine()
        except TimeoutError:
            state = "WARMING_UP"
        except Exception as exc:
            state, engine_error = "ERROR", str(exc)

    _render_sidebar(user, auth_service, repository, engine)

    if state == "ERROR":
        st.error(f"Không thể khởi tạo chatbot: {engine_error or 'lỗi không xác định'}")
        if st.button("Thử kiểm tra lại"):
            st.rerun()
        return
    if engine is None:
        st.info("Chatbot đang khởi tạo mô hình cục bộ. Quá trình này có thể mất một lúc.")
        if st.button("Kiểm tra trạng thái"):
            st.rerun()
        return

    _render_chat(user, engine, repository)


if __name__ == "__main__" or st.runtime.exists():
    main()
