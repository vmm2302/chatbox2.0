import React from 'react';
import { Monitor, Sun, Moon } from 'lucide-react';

/**
 * Sleek 3-way Theme Toggle Component:
 * - 'system': Tự động theo cấu hình hệ điều hành / máy tính (Mặc định)
 * - 'light': Nền Sáng
 * - 'dark': Nền Tối
 */
export default function ThemeToggle({ themeMode, currentTheme, onThemeChange, className = '' }) {
  const activeMode = themeMode || currentTheme || 'system';
  const options = [
    {
      id: 'system',
      label: 'Theo máy',
      icon: <Monitor className="w-3.5 h-3.5" />,
      tooltip: 'Tự động sáng/tối theo cấu hình máy tính',
    },
    {
      id: 'light',
      label: 'Sáng',
      icon: <Sun className="w-3.5 h-3.5" />,
      tooltip: 'Giao diện nền sáng',
    },
    {
      id: 'dark',
      label: 'Tối',
      icon: <Moon className="w-3.5 h-3.5" />,
      tooltip: 'Giao diện nền tối dịu mắt',
    },
  ];

  return (
    <div
      className={`inline-flex items-center p-1 rounded-2xl bg-slate-100/90 dark:bg-[#212121] border border-slate-200/80 dark:border-white/10 shadow-2xs ${className}`}
      title="Cài đặt giao diện Sáng / Tối"
    >
      {options.map((opt) => {
        const isActive = activeMode === opt.id;
        return (
          <button
            key={opt.id}
            type="button"
            onClick={() => onThemeChange(opt.id)}
            title={opt.tooltip}
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-xl text-xs font-bold transition-all cursor-pointer ${
              isActive
                ? 'bg-white dark:bg-[#2f2f2f] text-emerald-700 dark:text-white shadow-xs font-extrabold dark:border dark:border-white/10'
                : 'text-slate-500 dark:text-zinc-400 hover:text-slate-800 dark:hover:text-white hover:bg-white/50 dark:hover:bg-white/[0.06]'
            }`}
          >
            {opt.icon}
            <span className="hidden sm:inline">{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
}
