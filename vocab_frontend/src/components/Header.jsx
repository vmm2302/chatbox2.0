import React from 'react';
import {
  BookOpen,
  Sparkles,
} from 'lucide-react';
import ThemeToggle from './ThemeToggle';

export default function Header({ activeTab, setActiveTab, themeMode, onThemeChange }) {
  return (
    <header className="sticky top-0 z-40 bg-white/80 dark:bg-[#171717]/85 backdrop-blur-md border-b border-slate-200/80 dark:border-white/10 shadow-xs">
      <div className="w-full px-3 sm:px-5 lg:px-6">
        <div className="flex items-center justify-between gap-2 sm:gap-4 h-14 sm:h-16">
          
          {/* Logo & Brand */}
          <div
            className="flex items-center space-x-2.5 sm:space-x-3 cursor-pointer shrink-0"
            onClick={() => setActiveTab('chat')}
          >
            <div className="w-9 h-9 sm:w-11 sm:h-11 rounded-2xl bg-gradient-to-tr from-emerald-500 via-teal-500 to-cyan-500 flex items-center justify-center shadow-md shadow-emerald-500/20 text-white font-black text-lg sm:text-xl shrink-0">
              📚
            </div>
            <div className="min-w-0">
              <div className="flex items-center space-x-1.5 sm:space-x-2 shrink-0">
                <span className="text-base sm:text-lg lg:text-xl font-black tracking-tight text-slate-900 dark:text-white whitespace-nowrap">
                  Chatbot cho từ vựng <span className="text-emerald-600 dark:text-emerald-400">A1 - A2</span>
                </span>
                <span className="hidden sm:inline-flex px-2 py-0.5 text-[10px] sm:text-[11px] font-bold uppercase tracking-wider rounded-full bg-emerald-100 dark:bg-white/[0.08] text-emerald-800 dark:text-emerald-400 border border-emerald-200/60 dark:border-white/10 shrink-0 whitespace-nowrap">
                  CEFR A1–A2
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-zinc-400 font-medium hidden xl:block truncate">
                Trợ lý tra cứu & học từ vựng tiếng Anh cấp độ A1–A2
              </p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex items-center space-x-1 p-1 sm:p-1.5 rounded-2xl bg-slate-100/90 dark:bg-[#212121] border border-slate-200/60 dark:border-white/10 shrink-0">
            <button
              onClick={() => setActiveTab('chat')}
              className={`flex items-center space-x-1.5 px-2.5 sm:px-3.5 py-1.5 rounded-xl text-xs sm:text-sm font-bold transition-all duration-200 cursor-pointer whitespace-nowrap ${
                activeTab === 'chat'
                  ? 'bg-white dark:bg-[#2f2f2f] text-emerald-700 dark:text-white shadow-sm font-extrabold dark:border dark:border-white/10'
                  : 'text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-white hover:bg-white/60 dark:hover:bg-white/[0.06]'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-emerald-500 shrink-0" />
              <span>Tra cứu & Chat</span>
            </button>

            <button
              onClick={() => setActiveTab('discover')}
              className={`flex items-center space-x-1.5 px-2.5 sm:px-3.5 py-1.5 rounded-xl text-xs sm:text-sm font-bold transition-all duration-200 cursor-pointer whitespace-nowrap ${
                activeTab === 'discover'
                  ? 'bg-white dark:bg-[#2f2f2f] text-cyan-700 dark:text-white shadow-sm font-extrabold dark:border dark:border-white/10'
                  : 'text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-white hover:bg-white/60 dark:hover:bg-white/[0.06]'
              }`}
            >
              <BookOpen className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-cyan-500 shrink-0" />
              <span>Khám phá từ vựng</span>
            </button>
          </nav>

          {/* Right Area: Theme Switcher */}
          <div className="flex items-center shrink-0">
            {onThemeChange && (
              <ThemeToggle themeMode={themeMode} onThemeChange={onThemeChange} />
            )}
          </div>

        </div>
      </div>
    </header>
  );
}
