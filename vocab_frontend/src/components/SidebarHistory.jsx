import React, { useState, useEffect } from 'react';
import {
  Plus,
  Search,
  MessageSquare,
  Pin,
  PinOff,
  Trash2,
  Edit2,
  Check,
  X,
  Clock,
  Calendar,
  Sparkles,
  ChevronUp,
  Shield,
  LogOut,
  User,
  ArrowRight,
} from 'lucide-react';
import { getConversations, renameConversation, togglePinConversation, deleteConversation, clearAllConversations } from '../services/api';
import ConfirmModal from './ConfirmModal';

export default function SidebarHistory({
  currentUser,
  currentConvId,
  onSelectConversation,
  onNewChat,
  isOpen,
  onClose,
  onLogout,
  setActiveTab,
  onNavigateToAdmin,
}) {
  const [conversationsData, setConversationsData] = useState({ pinned: [], grouped: {}, total: 0 });
  const [search, setSearch] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [confirmModal, setConfirmModal] = useState({
    isOpen: false,
    title: '',
    message: '',
    confirmText: 'Xác nhận xóa',
    type: 'danger',
    onConfirm: null,
  });

  const isAdmin = currentUser?.role === 'admin';

  const loadConversations = async () => {
    if (!currentUser) return;
    setIsLoading(true);
    try {
      const data = await getConversations(currentUser.id, search);
      setConversationsData(data);
    } catch (err) {
      console.error('Failed to load conversations:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadConversations();
  }, [currentUser, currentConvId, search]);

  const handleTogglePin = async (e, convId) => {
    e.stopPropagation();
    try {
      await togglePinConversation(convId, currentUser.id);
      loadConversations();
    } catch (err) {
      console.error('Pin error:', err);
    }
  };

  const handleStartRename = (e, conv) => {
    e.stopPropagation();
    setEditingId(conv.id);
    setEditingTitle(conv.title);
  };

  const handleSaveRename = async (e, convId) => {
    e.stopPropagation();
    if (!editingTitle.trim()) return;
    try {
      await renameConversation(convId, currentUser.id, editingTitle.trim());
      setEditingId(null);
      loadConversations();
    } catch (err) {
      console.error('Rename error:', err);
    }
  };

  const handleDelete = (e, convId, convTitle) => {
    e.stopPropagation();
    const titleSnippet = convTitle ? ` "${convTitle}"` : '';
    setConfirmModal({
      isOpen: true,
      title: 'Xóa cuộc trò chuyện?',
      message: `Cuộc trò chuyện${titleSnippet} sẽ bị xóa vĩnh viễn khỏi danh sách lịch sử của bạn và không thể hoàn tác.`,
      confirmText: 'Xóa cuộc trò chuyện',
      type: 'danger',
      onConfirm: async () => {
        setConfirmModal((prev) => ({ ...prev, isOpen: false }));
        try {
          await deleteConversation(convId, currentUser.id);
          if (currentConvId === convId) {
            onNewChat();
          } else {
            loadConversations();
          }
        } catch (err) {
          console.error('Delete error:', err);
        }
      },
    });
  };

  const handleClearAll = () => {
    setConfirmModal({
      isOpen: true,
      title: 'Xóa toàn bộ lịch sử trò chuyện?',
      message: 'CẢNH BÁO NGUY HIỂM:\nToàn bộ danh sách cuộc trò chuyện và lịch sử học tập của bạn sẽ bị xóa sạch hoàn toàn khỏi hệ thống.\n\nBạn có chắc chắn muốn tiếp tục không?',
      confirmText: 'Xóa toàn bộ lịch sử',
      type: 'danger',
      onConfirm: async () => {
        setConfirmModal((prev) => ({ ...prev, isOpen: false }));
        try {
          await clearAllConversations(currentUser.id);
          onNewChat();
          loadConversations();
        } catch (err) {
          console.error('Clear all error:', err);
        }
      },
    });
  };

  const renderConvItem = (conv) => {
    const isActive = conv.id === currentConvId;
    const isEditing = editingId === conv.id;

    return (
      <div
        key={conv.id}
        onClick={() => {
          if (!isEditing) {
            onSelectConversation(conv.id);
            if (typeof window !== 'undefined' && window.innerWidth < 1024 && onClose) {
              onClose();
            }
          }
        }}
        className={`group relative flex items-center justify-between px-3 py-2.5 rounded-2xl text-xs sm:text-sm font-semibold cursor-pointer transition-all ${
          isActive
            ? 'bg-emerald-50 dark:bg-[#262626] text-emerald-950 dark:text-white font-extrabold border border-emerald-200/80 dark:border-white/15 shadow-2xs'
            : 'text-slate-600 dark:text-zinc-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100/80 dark:hover:bg-white/[0.06]'
        }`}
      >
        <div className="flex items-center space-x-2.5 overflow-hidden flex-1 mr-1">
          <MessageSquare className={`w-4 h-4 shrink-0 ${isActive ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400 dark:text-zinc-500'}`} />
          {isEditing ? (
            <input
              type="text"
              autoFocus
              value={editingTitle}
              onClick={(e) => e.stopPropagation()}
              onChange={(e) => setEditingTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSaveRename(e, conv.id);
                if (e.key === 'Escape') setEditingId(null);
              }}
              className="w-full bg-white dark:bg-[#2a2a2a] px-2 py-0.5 rounded-md border border-emerald-400 dark:border-emerald-500 text-xs font-bold text-slate-800 dark:text-zinc-100 focus:outline-hidden"
            />
          ) : (
            <span className="truncate">{conv.title}</span>
          )}
        </div>

        {/* Action icons on hover */}
        <div className="flex items-center space-x-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
          {isEditing ? (
            <button
              onClick={(e) => handleSaveRename(e, conv.id)}
              className="p-1 rounded-md text-emerald-700 dark:text-emerald-400 hover:bg-emerald-100 dark:hover:bg-emerald-950/60"
            >
              <Check className="w-3.5 h-3.5" />
            </button>
          ) : (
            <>
              <button
                onClick={(e) => handleTogglePin(e, conv.id)}
                title={conv.is_pinned ? 'Bỏ ghim' : 'Ghim đoạn chat'}
                className="p-1 rounded-md text-slate-400 hover:text-emerald-600 hover:bg-slate-200/60 dark:hover:bg-white/10"
              >
                {conv.is_pinned ? <PinOff className="w-3.5 h-3.5" /> : <Pin className="w-3.5 h-3.5" />}
              </button>
              <button
                onClick={(e) => handleStartRename(e, conv)}
                title="Đổi tên"
                className="p-1 rounded-md text-slate-400 hover:text-slate-700 dark:hover:text-zinc-200 hover:bg-slate-200/60 dark:hover:bg-white/10"
              >
                <Edit2 className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={(e) => handleDelete(e, conv.id, conv.title)}
                title="Xóa"
                className="p-1 rounded-md text-slate-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40 cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </>
          )}
        </div>
      </div>
    );
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 bg-slate-900/40 dark:bg-black/60 backdrop-blur-xs z-40 lg:hidden"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-40 bg-white dark:bg-[#171717] border-r border-slate-200/90 dark:border-white/10 shadow-lg lg:shadow-none flex flex-col transition-all duration-300 ease-in-out lg:static overflow-hidden ${
          isOpen
            ? 'w-72 sm:w-80 translate-x-0 opacity-100'
            : 'w-0 -translate-x-full opacity-0 pointer-events-none border-r-0 lg:translate-x-0'
        }`}
      >
        <div className="w-72 sm:w-80 h-full flex flex-col shrink-0">
        {/* Top Header: New Chat & Search */}
        <div className="p-4 border-b border-slate-100 dark:border-white/10 space-y-3">
          <button
            onClick={() => {
              onNewChat();
              if (typeof window !== 'undefined' && window.innerWidth < 1024 && onClose) {
                onClose();
              }
            }}
            className="w-full flex items-center justify-center space-x-2 py-3 px-4 rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 dark:from-[#212121] dark:to-[#212121] dark:hover:from-[#2a2a2a] dark:hover:to-[#2a2a2a] text-white font-extrabold text-sm shadow-md shadow-emerald-500/20 dark:shadow-none dark:border dark:border-white/10 active:scale-98 transition-all cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Đoạn chat mới</span>
          </button>

          <div className="relative flex items-center">
            <Search className="w-4 h-4 text-slate-400 dark:text-zinc-500 absolute left-3 pointer-events-none" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm kiếm đoạn chat..."
              className="w-full pl-9 pr-3 py-2 bg-slate-50 dark:bg-[#212121] rounded-xl border border-slate-200 dark:border-white/10 text-xs font-semibold text-slate-800 dark:text-[#ececec] placeholder-slate-400 dark:placeholder-zinc-500 focus:outline-hidden focus:border-emerald-500 dark:focus:border-white/30 transition-colors"
            />
          </div>
        </div>

        {/* Scrollable Conversation List: Scrolls independently */}
        <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-4 overscroll-contain">
          {/* Pinned conversations */}
          {conversationsData.pinned && conversationsData.pinned.length > 0 && (
            <div className="space-y-1">
              <div className="text-[11px] font-black uppercase tracking-wider text-slate-400 dark:text-zinc-500 px-3 py-1 flex items-center space-x-1">
                <Pin className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                <span>Đã ghim</span>
              </div>
              {conversationsData.pinned.map(renderConvItem)}
            </div>
          )}

          {/* Time groups */}
          {['Hôm nay', '7 ngày gần đây', 'Trước đó'].map((grpName) => {
            const items = conversationsData.grouped?.[grpName] || [];
            if (items.length === 0) return null;
            return (
              <div key={grpName} className="space-y-1">
                <div className="text-[11px] font-black uppercase tracking-wider text-slate-400 dark:text-zinc-500 px-3 py-1">
                  {grpName}
                </div>
                {items.map(renderConvItem)}
              </div>
            );
          })}

          {conversationsData.total === 0 && !isLoading && (
            <div className="text-center py-10 px-4 text-xs font-semibold text-slate-400 dark:text-zinc-500">
              Chưa có đoạn chat nào. Hãy bắt đầu bằng cách nhập câu hỏi mới!
            </div>
          )}
        </div>

        {/* User Summary Bar */}
        <div className="px-4 py-2 border-t border-slate-100 dark:border-white/10 flex items-center justify-between text-[11px] text-slate-400 dark:text-zinc-500 font-semibold shrink-0">
          <span>{conversationsData.total} cuộc trò chuyện</span>
          {conversationsData.total > 0 && (
            <button
              onClick={handleClearAll}
              title="Xóa toàn bộ lịch sử"
              className="text-slate-400 hover:text-red-600 dark:hover:text-red-400 transition-colors cursor-pointer"
            >
              Xóa tất cả
            </button>
          )}
        </div>

        {/* User Account Section (ChatGPT / Gemini Style) */}
        <div className="shrink-0 p-2.5 border-t border-slate-200/80 dark:border-white/10 bg-slate-50/90 dark:bg-[#171717] relative">
          <div
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center justify-between p-2 rounded-2xl hover:bg-white dark:hover:bg-[#212121] hover:shadow-xs border border-transparent hover:border-slate-200/80 dark:hover:border-white/10 transition-all cursor-pointer group"
          >
            <div className="flex items-center space-x-2.5 overflow-hidden">
              <div className={`w-9 h-9 rounded-xl text-white font-black text-sm flex items-center justify-center shrink-0 shadow-xs ${
                isAdmin ? 'bg-gradient-to-tr from-indigo-600 to-purple-600' : 'bg-gradient-to-tr from-emerald-600 to-teal-700'
              }`}>
                {currentUser?.display_name?.slice(0, 1)?.toUpperCase() || currentUser?.username?.slice(0, 1)?.toUpperCase() || 'U'}
              </div>
              <div className="text-left overflow-hidden">
                <div className="text-xs font-bold text-slate-800 dark:text-zinc-100 truncate max-w-[140px]">
                  {currentUser?.display_name || currentUser?.username}
                </div>
                <div className="text-[10px] font-semibold text-slate-400 dark:text-zinc-400 flex items-center space-x-1">
                  <span className={`inline-block w-1.5 h-1.5 rounded-full ${isAdmin ? 'bg-indigo-500' : 'bg-emerald-500'}`} />
                  <span>{isAdmin ? 'Quản trị viên' : 'Học viên'}</span>
                </div>
              </div>
            </div>

            <ChevronUp className={`w-4 h-4 text-slate-400 group-hover:text-slate-600 dark:group-hover:text-zinc-300 transition-transform duration-200 ${showUserMenu ? 'rotate-180' : ''}`} />
          </div>

          {/* User Popover Menu */}
          {showUserMenu && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setShowUserMenu(false)}
              />
              <div className="absolute bottom-full left-2 right-2 mb-2 bg-white dark:bg-[#212121] rounded-2xl shadow-2xl border border-slate-200/90 dark:border-white/10 p-2 z-50 animate-in fade-in zoom-in-95 duration-150">
                {/* Header in popover */}
                <div className="px-3 py-2 border-b border-slate-100 dark:border-white/10 mb-1">
                  <div className="text-xs font-black text-slate-900 dark:text-white truncate">
                    {currentUser?.display_name || currentUser?.username}
                  </div>
                  <div className="text-[10px] text-slate-400 dark:text-zinc-400 font-mono">
                    @{currentUser?.username} · {isAdmin ? 'Quản trị viên' : 'Học viên'}
                  </div>
                </div>

                {/* Menu items */}
                {isAdmin && (
                  <button
                    onClick={() => {
                      setShowUserMenu(false);
                      if (typeof window !== 'undefined' && window.innerWidth < 1024 && onClose) {
                        onClose();
                      }
                      if (onNavigateToAdmin) {
                        onNavigateToAdmin();
                      } else {
                        window.location.href = window.location.pathname + '?page=admin';
                      }
                    }}
                    className="w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-bold text-indigo-700 dark:text-indigo-300 bg-indigo-50/70 dark:bg-indigo-950/40 hover:bg-indigo-100 dark:hover:bg-indigo-900/40 transition-colors cursor-pointer mb-1 border border-indigo-100 dark:border-indigo-800/40"
                    title="Chuyển đến Bảng điều khiển Quản trị hệ thống"
                  >
                    <div className="flex items-center space-x-2">
                      <Shield className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                      <span>Quản trị hệ thống</span>
                    </div>
                    <ArrowRight className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400" />
                  </button>
                )}

                {setActiveTab && (
                  <button
                    onClick={() => {
                      setActiveTab('flashcards');
                      setShowUserMenu(false);
                      if (typeof window !== 'undefined' && window.innerWidth < 1024 && onClose) {
                        onClose();
                      }
                    }}
                    className="w-full flex items-center space-x-2 px-3 py-2 rounded-xl text-xs font-bold text-slate-700 dark:text-zinc-200 hover:text-teal-700 dark:hover:text-teal-400 hover:bg-teal-50 dark:hover:bg-white/[0.06] transition-colors cursor-pointer"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-teal-600 dark:text-teal-400" />
                    <span>Sổ tay từ vựng</span>
                  </button>
                )}

                <div className="border-t border-slate-100 dark:border-white/10 my-1" />

                {conversationsData.total > 0 && (
                  <button
                    onClick={() => {
                      setShowUserMenu(false);
                      handleClearAll();
                    }}
                    className="w-full flex items-center space-x-2 px-3 py-2 rounded-xl text-xs font-bold text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors cursor-pointer"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Xóa toàn bộ lịch sử</span>
                  </button>
                )}

                {onLogout && (
                  <button
                    onClick={() => {
                      setShowUserMenu(false);
                      onLogout();
                    }}
                    className="w-full flex items-center space-x-2 px-3 py-2 rounded-xl text-xs font-bold text-rose-700 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors cursor-pointer"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    <span>Đăng xuất</span>
                  </button>
                )}
              </div>
            </>
          )}
        </div>
        </div>
      </aside>

      {/* In-App Modern Confirmation Modal */}
      <ConfirmModal
        isOpen={confirmModal.isOpen}
        title={confirmModal.title}
        message={confirmModal.message}
        confirmText={confirmModal.confirmText}
        type={confirmModal.type}
        onConfirm={confirmModal.onConfirm}
        onClose={() => setConfirmModal((prev) => ({ ...prev, isOpen: false }))}
      />
    </>
  );
}
