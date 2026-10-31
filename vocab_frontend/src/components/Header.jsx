import React from 'react';
import {
  BookOpen,
  Sparkles,
  Layers,
  Bookmark,
  CheckCircle2,
} from 'lucide-react';
import ThemeToggle from './ThemeToggle';

export default function Header({ activeTab, setActiveTab, stats, themeMode, onThemeChange }) {
  return (
    <header className="sticky top-0 z-40 bg-white/80 dark:bg-[#171717]/85 backdrop-blur-md border-b border-slate-200/80 dark:border-white/10 shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 sm:h-20">
          
          {/* Logo & Brand */}
          <div
            className="flex items-center space-x-3 cursor-pointer"
            onClick={() => setActiveTab('chat')}
          >
            <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-2xl bg-gradient-to-tr from-emerald-500 via-teal-500 to-cyan-500 flex items-center justify-center shadow-md shadow-emerald-500/20 text-white font-black text-xl">
              📚
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-xl sm:text-2xl font-black tracking-tight text-slate-900 dark:text-white">
                  Vocab<span className="text-emerald-600 dark:text-emerald-400">Chat</span>
                </span>
                <span className="px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider rounded-full bg-emerald-100 dark:bg-white/[0.08] text-emerald-800 dark:text-emerald-400 border border-emerald-200/60 dark:border-white/10">
                  CEFR A1–B2
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-zinc-400 font-medium hidden sm:block">
                Trợ lý tra cứu & học từ vựng tiếng Anh tương tác thông minh
              </p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex items-center space-x-1 sm:space-x-2 bg-slate-100/90 dark:bg-[#212121] p-1.5 rounded-2xl border border-slate-200/60 dark:border-white/10">
            <button
              onClick={() => setActiveTab('chat')}
              className={`flex items-center space-x-1.5 sm:space-x-2 px-3 sm:px-4 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all duration-200 cursor-pointer ${
                activeTab === 'chat'
                  ? 'bg-white dark:bg-[#2f2f2f] text-emerald-700 dark:text-white shadow-sm font-extrabold dark:border dark:border-white/10'
                  : 'text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-white hover:bg-white/60 dark:hover:bg-white/[0.06]'
              }`}
            >
              <Sparkles className="w-4 h-4 text-emerald-500" />
              <span>Tra cứu & Chat</span>
            </button>

            <button
              onClick={() => setActiveTab('flashcards')}
              className={`flex items-center space-x-1.5 sm:space-x-2 px-3 sm:px-4 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all duration-200 cursor-pointer ${
                activeTab === 'flashcards'
                  ? 'bg-white dark:bg-[#2f2f2f] text-teal-700 dark:text-white shadow-sm font-extrabold dark:border dark:border-white/10'
                  : 'text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-white hover:bg-white/60 dark:hover:bg-white/[0.06]'
              }`}
            >
              <Layers className="w-4 h-4 text-teal-500" />
              <span>Sổ tay</span>
              {stats?.total_saved > 0 && (
                <span className="ml-1 px-1.5 py-0.2 text-[10px] font-black rounded-full bg-emerald-500 text-white">
                  {stats.total_saved}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('discover')}
              className={`flex items-center space-x-1.5 sm:space-x-2 px-3 sm:px-4 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all duration-200 hidden md:flex cursor-pointer ${
                activeTab === 'discover'
                  ? 'bg-white dark:bg-[#2f2f2f] text-cyan-700 dark:text-white shadow-sm font-extrabold dark:border dark:border-white/10'
                  : 'text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-white hover:bg-white/60 dark:hover:bg-white/[0.06]'
              }`}
            >
              <BookOpen className="w-4 h-4 text-cyan-500" />
              <span>Khám phá</span>
            </button>
          </nav>

          {/* Right Area: Stats Pill & Theme Switcher */}
          <div className="flex items-center space-x-2 sm:space-x-3">
            {/* Quick Stats Pill */}
            <div className="hidden lg:flex items-center space-x-3 bg-white dark:bg-[#212121] px-3 py-1.5 rounded-2xl border border-slate-200 dark:border-white/10 shadow-2xs">
              <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-600 dark:text-zinc-300">
                <Bookmark className="w-3.5 h-3.5 text-amber-500" />
                <span>Đã lưu: <b className="text-slate-900 dark:text-white font-bold">{stats?.total_saved || 0}</b></span>
              </div>
              <div className="w-px h-3.5 bg-slate-200 dark:bg-white/10" />
              <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-600 dark:text-zinc-300">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                <span>Đã thuộc: <b className="text-emerald-700 dark:text-emerald-400 font-bold">{stats?.mastered || 0}</b></span>
              </div>
            </div>

            {/* Theme Toggle (System / Light / Dark) */}
            {onThemeChange && (
              <ThemeToggle themeMode={themeMode} onThemeChange={onThemeChange} />
            )}
          </div>

        </div>
      </div>
    </header>
  );
}
