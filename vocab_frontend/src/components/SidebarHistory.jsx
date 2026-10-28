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
  ArrowUpRight,
} from 'lucide-react';
import { getConversations, renameConversation, togglePinConversation, deleteConversation, clearAllConversations } from '../services/api';

export default function SidebarHistory({
  currentUser,
  currentConvId,
  onSelectConversation,
  onNewChat,
  isOpen,
  onClose,
  onLogout,
  setActiveTab,
}) {
  const [conversationsData, setConversationsData] = useState({ pinned: [], grouped: {}, total: 0 });
  const [search, setSearch] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);

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

  const handleDelete = async (e, convId) => {
    e.stopPropagation();
    if (!confirm('Bạn có chắc muốn xóa cuộc trò chuyện này?')) return;
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
  };

  const handleClearAll = async () => {
    if (!confirm('CẢNH BÁO: Toàn bộ lịch sử trò chuyện của bạn sẽ bị xóa vĩnh viễn. Bạn có chắc chắn?')) return;
    try {
      await clearAllConversations(currentUser.id);
      onNewChat();
      loadConversations();
    } catch (err) {
      console.error('Clear all error:', err);
    }
  };

  const renderConvItem = (conv) => {
    const isActive = conv.id === currentConvId;
    const isEditing = editingId === conv.id;

    return (
      <div
        key={conv.id}
        onClick={() => !isEditing && onSelectConversation(conv.id)}
        className={`group relative flex items-center justify-between px-3 py-2.5 rounded-2xl text-xs sm:text-sm font-semibold cursor-pointer transition-all ${
          isActive
            ? 'bg-emerald-50 text-emerald-950 font-extrabold border border-emerald-200/80 shadow-2xs'
            : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80'
        }`}
      >
        <div className="flex items-center space-x-2.5 overflow-hidden flex-1 mr-1">
          <MessageSquare className={`w-4 h-4 shrink-0 ${isActive ? 'text-emerald-600' : 'text-slate-400'}`} />
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
              className="w-full bg-white px-2 py-0.5 rounded-md border border-emerald-400 text-xs font-bold text-slate-800 focus:outline-hidden"
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
              className="p-1 rounded-md text-emerald-700 hover:bg-emerald-100"
            >
              <Check className="w-3.5 h-3.5" />
            </button>
          ) : (
            <>
              <button
                onClick={(e) => handleTogglePin(e, conv.id)}
                title={conv.is_pinned ? 'Bỏ ghim' : 'Ghim đoạn chat'}
                className="p-1 rounded-md text-slate-400 hover:text-emerald-600 hover:bg-slate-200/60"
              >
                {conv.is_pinned ? <PinOff className="w-3.5 h-3.5" /> : <Pin className="w-3.5 h-3.5" />}
              </button>
              <button
                onClick={(e) => handleStartRename(e, conv)}
                title="Đổi tên"
                className="p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-200/60"
              >
                <Edit2 className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={(e) => handleDelete(e, conv.id)}
                title="Xóa"
                className="p-1 rounded-md text-slate-400 hover:text-red-600 hover:bg-red-50"
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
          className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-40 lg:hidden"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-40 bg-white border-r border-slate-200/90 shadow-lg lg:shadow-none flex flex-col transition-all duration-300 ease-in-out lg:static overflow-hidden ${
          isOpen
            ? 'w-72 sm:w-80 translate-x-0 opacity-100'
            : 'w-0 -translate-x-full opacity-0 pointer-events-none border-r-0 lg:translate-x-0'
        }`}
      >
        <div className="w-72 sm:w-80 h-full flex flex-col shrink-0">
        {/* Top Header: New Chat & Search */}
        <div className="p-4 border-b border-slate-100 space-y-3">
          <button
            onClick={() => {
              onNewChat();
              if (onClose) onClose();
            }}
            className="w-full flex items-center justify-center space-x-2 py-3 px-4 rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white font-extrabold text-sm shadow-md shadow-emerald-500/20 active:scale-98 transition-all cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Đoạn chat mới</span>
          </button>

          <div className="relative flex items-center">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 pointer-events-none" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm kiếm đoạn chat..."
              className="w-full pl-9 pr-3 py-2 bg-slate-50 rounded-xl border border-slate-200 text-xs font-semibold text-slate-800 focus:outline-hidden focus:border-emerald-500 transition-colors"
            />
          </div>
        </div>

        {/* Scrollable Conversation List: Scrolls independently */}
        <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-4 overscroll-contain">
          {/* Pinned conversations */}
          {conversationsData.pinned && conversationsData.pinned.length > 0 && (
            <div className="space-y-1">
              <div className="text-[11px] font-black uppercase tracking-wider text-slate-400 px-3 py-1 flex items-center space-x-1">
                <Pin className="w-3 h-3 text-emerald-600" />
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
                <div className="text-[11px] font-black uppercase tracking-wider text-slate-400 px-3 py-1">
                  {grpName}
                </div>
                {items.map(renderConvItem)}
              </div>
            );
          })}

          {conversationsData.total === 0 && !isLoading && (
            <div className="text-center py-10 px-4 text-xs font-semibold text-slate-400">
              Chưa có đoạn chat nào. Hãy bắt đầu bằng cách nhập câu hỏi mới!
            </div>
          )}
        </div>

        {/* User Summary Bar */}
        <div className="px-4 py-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400 font-semibold shrink-0">
          <span>{conversationsData.total} cuộc trò chuyện</span>
          {conversationsData.total > 0 && (
            <button
              onClick={handleClearAll}
              title="Xóa toàn bộ lịch sử"
              className="text-slate-400 hover:text-red-600 transition-colors cursor-pointer"
            >
              Xóa tất cả
            </button>
          )}
        </div>

        {/* User Account Section (ChatGPT / Gemini Style) */}
        <div className="shrink-0 p-2.5 border-t border-slate-200/80 bg-slate-50/90 relative">
          <div
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center justify-between p-2 rounded-2xl hover:bg-white hover:shadow-xs border border-transparent hover:border-slate-200/80 transition-all cursor-pointer group"
          >
            <div className="flex items-center space-x-2.5 overflow-hidden">
              <div className={`w-9 h-9 rounded-xl text-white font-black text-sm flex items-center justify-center shrink-0 shadow-xs ${
                isAdmin ? 'bg-gradient-to-tr from-indigo-600 to-purple-600' : 'bg-gradient-to-tr from-emerald-600 to-teal-700'
              }`}>
                {currentUser?.display_name?.slice(0, 1)?.toUpperCase() || currentUser?.username?.slice(0, 1)?.toUpperCase() || 'U'}
              </div>
              <div className="text-left overflow-hidden">
                <div className="text-xs font-bold text-slate-800 truncate max-w-[140px]">
                  {currentUser?.display_name || currentUser?.username}
                </div>
                <div className="text-[10px] font-semibold text-slate-400 flex items-center space-x-1">
                  <span className={`inline-block w-1.5 h-1.5 rounded-full ${isAdmin ? 'bg-indigo-500' : 'bg-emerald-500'}`} />
                  <span>{isAdmin ? 'Quản trị viên' : 'Học viên'}</span>
                </div>
              </div>
            </div>

            <ChevronUp className={`w-4 h-4 text-slate-400 group-hover:text-slate-600 transition-transform duration-200 ${showUserMenu ? 'rotate-180' : ''}`} />
          </div>

          {/* User Popover Menu */}
          {showUserMenu && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setShowUserMenu(false)}
              />
              <div className="absolute bottom-full left-2 right-2 mb-2 bg-white rounded-2xl shadow-xl border border-slate-200/90 p-2 z-50 animate-in fade-in zoom-in-95 duration-150">
                {/* Header in popover */}
                <div className="px-3 py-2 border-b border-slate-100 mb-1">
                  <div className="text-xs font-black text-slate-900 truncate">
                    {currentUser?.display_name || currentUser?.username}
                  </div>
                  <div className="text-[10px] text-slate-400 font-mono">
                    @{currentUser?.username} · {isAdmin ? 'Quản trị viên' : 'Học viên'}
                  </div>
                </div>

                {/* Menu items */}
                {isAdmin && (
                  <button
                    onClick={() => {
                      window.open(window.location.pathname + '?page=admin', '_blank');
                      setShowUserMenu(false);
                      if (onClose) onClose();
                    }}
                    className="w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-bold text-indigo-700 bg-indigo-50/70 hover:bg-indigo-100 transition-colors cursor-pointer mb-1 border border-indigo-100"
                    title="Mở Bảng điều khiển Quản trị hệ thống trong trang mới"
                  >
                    <div className="flex items-center space-x-2">
                      <Shield className="w-3.5 h-3.5 text-indigo-600" />
                      <span>Quản trị hệ thống</span>
                    </div>
                    <ArrowUpRight className="w-3.5 h-3.5 text-indigo-500" />
                  </button>
                )}

                {setActiveTab && (
                  <button
                    onClick={() => {
                      setActiveTab('flashcards');
                      setShowUserMenu(false);
                      if (onClose) onClose();
                    }}
                    className="w-full flex items-center space-x-2 px-3 py-2 rounded-xl text-xs font-bold text-slate-700 hover:text-teal-700 hover:bg-teal-50 transition-colors cursor-pointer"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-teal-600" />
                    <span>Sổ tay từ vựng</span>
                  </button>
                )}

                <div className="border-t border-slate-100 my-1" />

                {conversationsData.total > 0 && (
                  <button
                    onClick={() => {
                      setShowUserMenu(false);
                      handleClearAll();
                    }}
                    className="w-full flex items-center space-x-2 px-3 py-2 rounded-xl text-xs font-bold text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
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
                    className="w-full flex items-center space-x-2 px-3 py-2 rounded-xl text-xs font-bold text-rose-700 hover:bg-rose-50 transition-colors cursor-pointer"
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
    </>
  );
}
