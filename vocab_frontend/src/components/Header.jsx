import React from 'react';
import {
  BookOpen,
  Sparkles,
} from 'lucide-react';
import ThemeToggle from './ThemeToggle';

export default function Header({ activeTab, setActiveTab, themeMode, onThemeChange }) {
  return (
    <header className="sticky top-0 z-40 bg-white/80 dark:bg-[#171717]/85 backdrop-blur-md border-b border-slate-200/80 dark:border-white/10 shadow-xs">
      <div className="w-full px-4 sm:px-6 lg:px-8">
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
                  Chatbot cho từ vựng <span className="text-emerald-600 dark:text-emerald-400">A1 - A2</span>
                </span>
                <span className="px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider rounded-full bg-emerald-100 dark:bg-white/[0.08] text-emerald-800 dark:text-emerald-400 border border-emerald-200/60 dark:border-white/10">
                  CEFR A1–A2
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-zinc-400 font-medium hidden sm:block">
                Trợ lý tra cứu & học từ vựng tiếng Anh cấp độ A1–A2
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
              onClick={() => setActiveTab('discover')}
              className={`flex items-center space-x-1.5 sm:space-x-2 px-3 sm:px-4 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all duration-200 cursor-pointer ${
                activeTab === 'discover'
                  ? 'bg-white dark:bg-[#2f2f2f] text-cyan-700 dark:text-white shadow-sm font-extrabold dark:border dark:border-white/10'
                  : 'text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-white hover:bg-white/60 dark:hover:bg-white/[0.06]'
              }`}
            >
              <BookOpen className="w-4 h-4 text-cyan-500" />
              <span>Khám phá A1–A2</span>
            </button>
          </nav>

          {/* Right Area: Theme Switcher */}
          <div className="flex items-center space-x-2 sm:space-x-3">
            {onThemeChange && (
              <ThemeToggle themeMode={themeMode} onThemeChange={onThemeChange} />
            )}
          </div>

        </div>
      </div>
    </header>
  );
}
