import React, { useEffect } from 'react';
import {
  Trash2,
  AlertTriangle,
  AlertCircle,
  ShieldAlert,
  X,
  Loader2,
} from 'lucide-react';

/**
 * Reusable In-App Modern Confirmation & Alert Dialog.
 * Replaces native browser window.confirm() and window.alert() with a sleek glassmorphic modal.
 */
export default function ConfirmModal({
  isOpen,
  title = 'Xác nhận hành động',
  message,
  confirmText = 'Xác nhận',
  cancelText = 'Hủy bỏ',
  type = 'danger', // 'danger' | 'warning' | 'info'
  showCancel = true,
  isLoading = false,
  onConfirm,
  onClose,
}) {
  // Listen to Escape key to close modal
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && !isLoading) {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isLoading, onClose]);

  if (!isOpen) return null;

  // Icon & Theme Styling based on action type
  const themeConfig = {
    danger: {
      badgeBg: 'bg-rose-100 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400 ring-8 ring-rose-50/80 dark:ring-rose-950/20',
      icon: <Trash2 className="w-7 h-7 text-rose-600 dark:text-rose-400" />,
      btnBg: 'bg-gradient-to-r from-rose-500 to-red-600 hover:from-rose-600 hover:to-red-700 text-white shadow-md shadow-rose-500/25',
    },
    warning: {
      badgeBg: 'bg-amber-100 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400 ring-8 ring-amber-50/80 dark:ring-amber-950/20',
      icon: <AlertTriangle className="w-7 h-7 text-amber-600 dark:text-amber-400" />,
      btnBg: 'bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 text-white shadow-md shadow-amber-500/25',
    },
    info: {
      badgeBg: 'bg-indigo-100 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 ring-8 ring-indigo-50/80 dark:ring-indigo-950/20',
      icon: <ShieldAlert className="w-7 h-7 text-indigo-600 dark:text-indigo-400" />,
      btnBg: 'bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white shadow-md shadow-indigo-500/25',
    },
  }[type] || {
    badgeBg: 'bg-rose-100 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400 ring-8 ring-rose-50/80 dark:ring-rose-950/20',
    icon: <AlertCircle className="w-7 h-7 text-rose-600 dark:text-rose-400" />,
    btnBg: 'bg-gradient-to-r from-rose-500 to-red-600 hover:from-rose-600 hover:to-red-700 text-white shadow-md shadow-rose-500/25',
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-slate-900/60 dark:bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-150"
      onClick={() => {
        if (!isLoading) onClose();
      }}
    >
      <div
        className="bg-white dark:bg-[#212121] rounded-3xl max-w-md w-full p-6 sm:p-7 shadow-2xl dark:shadow-black/70 border border-slate-100 dark:border-white/10 relative animate-in zoom-in-95 duration-150 text-center"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Close Button (X) */}
        {!isLoading && (
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-1.5 rounded-xl text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/10 transition-colors cursor-pointer"
            title="Đóng (Esc)"
          >
            <X className="w-4 h-4" />
          </button>
        )}

        {/* Central Icon Badge */}
        <div className="flex justify-center mb-4">
          <div className={`w-14 h-14 rounded-2xl flex items-center justify-center shadow-xs ${themeConfig.badgeBg}`}>
            {themeConfig.icon}
          </div>
        </div>

        {/* Modal Title */}
        <h3 className="text-lg sm:text-xl font-black text-slate-900 dark:text-white tracking-tight mb-2">
          {title}
        </h3>

        {/* Modal Description / Message */}
        <div className="text-xs sm:text-sm text-slate-500 dark:text-zinc-400 leading-relaxed font-medium mb-6 whitespace-pre-line px-2">
          {message}
        </div>

        {/* Action Buttons */}
        <div className={`flex items-center gap-3 ${showCancel ? 'justify-end sm:justify-center' : 'justify-center'}`}>
          {showCancel && (
            <button
              type="button"
              disabled={isLoading}
              onClick={onClose}
              className="flex-1 px-4 py-2.5 rounded-2xl bg-slate-100 dark:bg-[#2a2a2a] hover:bg-slate-200/80 dark:hover:bg-[#333333] text-slate-700 dark:text-zinc-200 font-bold text-xs sm:text-sm transition-all cursor-pointer border border-slate-200/60 dark:border-white/10 active:scale-98 disabled:opacity-50"
            >
              {cancelText}
            </button>
          )}

          <button
            type="button"
            disabled={isLoading}
            onClick={() => {
              if (onConfirm) onConfirm();
            }}
            className={`flex-1 flex items-center justify-center space-x-1.5 px-4 py-2.5 rounded-2xl font-bold text-xs sm:text-sm transition-all cursor-pointer active:scale-98 disabled:opacity-50 ${themeConfig.btnBg}`}
          >
            {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
            <span>{confirmText}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
