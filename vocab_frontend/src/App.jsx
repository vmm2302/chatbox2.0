import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import ChatView from './components/ChatView';
import FlashcardView from './components/FlashcardView';
import DiscoveryView from './components/DiscoveryView';
import AdminPanel from './components/AdminPanel';
import AuthPage from './components/AuthPage';
import ErrorBoundary from './components/ErrorBoundary';
import ThemeToggle from './components/ThemeToggle';
import { getStats, verifySession } from './services/api';
import { getInitialTheme, applyTheme, subscribeSystemTheme, THEME_STORAGE_KEY } from './utils/theme';

export default function App() {
  const [currentUser, setCurrentUser] = useState(() => {
    try {
      const saved = localStorage.getItem('vocab_chat_user');
      return saved ? JSON.parse(saved) : null;
    } catch (e) {
      return null;
    }
  });

  const [themeMode, setThemeMode] = useState(getInitialTheme);

  // Auto-apply theme and listen to OS system changes (prefers-color-scheme)
  useEffect(() => {
    applyTheme(themeMode);

    if (themeMode !== 'system') return;

    const unsubscribe = subscribeSystemTheme(() => {
      applyTheme('system');
    });

    return unsubscribe;
  }, [themeMode]);

  const handleThemeChange = (newMode) => {
    setThemeMode(newMode);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, newMode);
    } catch (e) {}
    applyTheme(newMode);
  };

  const [isAdminPage, setIsAdminPage] = useState(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      return params.get('page') === 'admin';
    } catch (e) {
      return false;
    }
  });

  // Listen to popstate (browser back / forward buttons)
  useEffect(() => {
    const handlePopState = () => {
      try {
        const params = new URLSearchParams(window.location.search);
        setIsAdminPage(params.get('page') === 'admin');
      } catch (e) {}
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const clearAdminQueryParam = () => {
    try {
      const url = new URL(window.location.href);
      if (url.searchParams.has('page')) {
        url.searchParams.delete('page');
        window.history.replaceState({ page: 'chat' }, '', url.pathname + (url.search ? url.search : ''));
      }
    } catch (e) {
      try {
        window.history.replaceState({ page: 'chat' }, '', window.location.pathname);
      } catch (err) {}
    }
  };

  const handleNavigateToAdmin = () => {
    setIsAdminPage(true);
    try {
      window.history.pushState({ page: 'admin' }, '', window.location.pathname + '?page=admin');
    } catch (e) {}
  };

  const handleNavigateToHome = () => {
    setIsAdminPage(false);
    clearAdminQueryParam();
  };

  const [activeTab, setActiveTab] = useState('chat');
  const [selectedLevel, setSelectedLevel] = useState('Tất cả');
  const [stats, setStats] = useState({ total_saved: 0, mastered: 0, learning: 0, by_level: {} });
  const [searchTriggerWord, setSearchTriggerWord] = useState('');

  const refreshStats = async () => {
    if (!currentUser) return;
    try {
      const data = await getStats(currentUser.id);
      setStats(data);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  };

  useEffect(() => {
    if (currentUser?.id) {
      verifySession(currentUser.id).then((res) => {
        if (!res) {
          handleLogout();
        } else {
          refreshStats();
        }
      }).catch(() => {
        refreshStats();
      });
    }
  }, [currentUser]);

  const handleLoginSuccess = (user) => {
    setCurrentUser(user);
    try {
      localStorage.setItem('vocab_chat_user', JSON.stringify(user));
    } catch (e) {
      console.error('Failed to persist user in storage:', e);
    }
    // If the logged-in user is not an admin, ensure they never land on ?page=admin
    if (user?.role !== 'admin') {
      setIsAdminPage(false);
      clearAdminQueryParam();
    }
  };

  const handleLogout = () => {
    setCurrentUser(null);
    setIsAdminPage(false);
    try {
      localStorage.removeItem('vocab_chat_user');
    } catch (e) {
      console.error('Failed to clear storage:', e);
    }
    setActiveTab('chat');
    // Clear URL query parameters so the address bar cleanly returns to /
    clearAdminQueryParam();
  };

  const handleSelectWordFromDiscovery = (word) => {
    setSearchTriggerWord(word);
    setActiveTab('chat');
  };

  // MANDATORY AUTH GATE:
  // If user is not logged in, show the login & registration gate.
  // The user cannot access vocabulary lookup without logging in.
  if (!currentUser) {
    return (
      <AuthPage
        onLoginSuccess={handleLoginSuccess}
        themeMode={themeMode}
        onThemeChange={handleThemeChange}
      />
    );
  }

  // STANDALONE ADMIN PAGE:
  // When opened via ?page=admin, renders dedicated Admin Console without the student Header
  if (isAdminPage) {
    if (currentUser?.role !== 'admin') {
      return (
        <div className="min-h-screen bg-slate-50 dark:bg-[#171717] flex flex-col items-center justify-center p-6 text-center text-slate-900 dark:text-[#ececec]">
          <div className="w-16 h-16 rounded-3xl bg-rose-100 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400 flex items-center justify-center text-3xl mb-4 shadow-sm">
            🚫
          </div>
          <h1 className="text-xl font-black text-slate-800 dark:text-white mb-2">Truy Cập Bị Từ Chối</h1>
          <p className="text-sm text-slate-500 dark:text-zinc-400 max-w-md mb-6">
            Bạn cần đăng nhập với vai trò Quản trị viên (Admin) để truy cập Bảng điều khiển quản trị hệ thống.
          </p>
          <button
            onClick={handleNavigateToHome}
            className="px-5 py-2.5 rounded-xl bg-slate-900 dark:bg-white dark:text-black text-white font-bold text-sm shadow-md hover:bg-slate-800 dark:hover:bg-zinc-200 transition-colors cursor-pointer"
          >
            ← Quay lại Trang Chính
          </button>
        </div>
      );
    }

    return (
      <div className="h-screen max-h-screen overflow-hidden bg-gradient-to-b from-slate-50 via-slate-100/50 to-slate-200/40 dark:from-[#171717] dark:via-[#171717] dark:to-[#171717] text-slate-900 dark:text-[#ececec] flex flex-col font-sans">
        {/* Dedicated Admin Header */}
        <header className="sticky top-0 z-40 bg-white/95 dark:bg-[#171717]/95 backdrop-blur-md border-b border-slate-200/80 dark:border-white/10 shadow-xs shrink-0">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-16 sm:h-20">
              {/* Admin Brand */}
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-2xl bg-gradient-to-tr from-indigo-600 via-purple-600 to-indigo-700 flex items-center justify-center shadow-md shadow-indigo-500/20 text-white font-black text-xl">
                  🛡️
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-xl sm:text-2xl font-black tracking-tight text-slate-900 dark:text-white">
                      Vocab<span className="text-indigo-600 dark:text-indigo-400">Admin</span>
                    </span>
                    <span className="px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider rounded-full bg-indigo-100 dark:bg-indigo-950/70 text-indigo-800 dark:text-indigo-300 border border-indigo-200/60 dark:border-indigo-800/60">
                      Portal Quản Trị
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-zinc-400 font-medium hidden sm:block">
                    Hệ thống quản trị tài khoản, cơ sở tri thức & giám sát AI trung tâm
                  </p>
                </div>
              </div>

              {/* Admin Actions */}
              <div className="flex items-center space-x-2 sm:space-x-3">
                <button
                  onClick={handleNavigateToHome}
                  className="flex items-center space-x-2 px-3.5 sm:px-4 py-2 rounded-xl bg-slate-100 dark:bg-[#262626] hover:bg-slate-200 dark:hover:bg-[#2f2f2f] text-slate-700 dark:text-[#ececec] text-xs sm:text-sm font-bold transition-all cursor-pointer border border-slate-200 dark:border-white/10"
                  title="Quay lại ứng dụng tra cứu từ vựng"
                >
                  <span>← Quay lại ứng dụng chính</span>
                </button>

                {/* Theme Toggle in Admin Portal */}
                <ThemeToggle themeMode={themeMode} onThemeChange={handleThemeChange} />

                <div className="hidden sm:flex items-center space-x-2 bg-slate-50 dark:bg-[#212121] px-3 py-1.5 rounded-2xl border border-slate-200 dark:border-white/10">
                  <div className="w-7 h-7 rounded-lg bg-indigo-600 text-white text-xs font-black flex items-center justify-center">
                    {currentUser?.username?.slice(0, 1)?.toUpperCase() || 'A'}
                  </div>
                  <div className="text-left text-xs">
                    <div className="font-bold text-slate-800 dark:text-zinc-100 leading-tight">
                      {currentUser?.display_name || currentUser?.username}
                    </div>
                    <div className="text-[10px] text-indigo-600 dark:text-indigo-400 font-bold">
                      Quản trị viên
                    </div>
                  </div>
                </div>

                <button
                  onClick={handleLogout}
                  className="p-2 sm:px-3 sm:py-2 rounded-xl text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 border border-transparent hover:border-rose-200 dark:hover:border-rose-900/40 text-xs font-bold transition-all cursor-pointer flex items-center space-x-1.5"
                  title="Đăng xuất khỏi hệ thống"
                >
                  <span>Đăng xuất</span>
                </button>
              </div>
            </div>
          </div>
        </header>

        {/* Dedicated Admin Main Content */}
        <main className="flex-1 min-h-0 overflow-y-auto">
          <ErrorBoundary onNavigateHome={handleNavigateToHome} onReset={() => window.location.reload()}>
            <AdminPanel currentUser={currentUser} />
          </ErrorBoundary>
        </main>
      </div>
    );
  }

  return (
    <div className="h-screen max-h-screen overflow-hidden bg-gradient-to-b from-slate-50 via-emerald-50/20 to-teal-50/30 dark:from-[#212121] dark:via-[#212121] dark:to-[#212121] text-slate-900 dark:text-[#ececec] flex flex-col font-sans">
      
      {/* Main App Navigation Bar (Clean: No admin tab, No top account dropdown) */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        stats={stats}
        themeMode={themeMode}
        onThemeChange={handleThemeChange}
      />

      {/* Main Content Area */}
      <main className={`flex-1 min-h-0 ${activeTab === 'chat' ? 'overflow-hidden' : 'overflow-y-auto'}`}>
        <ErrorBoundary onNavigateHome={() => setActiveTab('chat')} onReset={() => window.location.reload()}>
          {activeTab === 'chat' && (
            <ChatView
              currentUser={currentUser}
              selectedLevel={selectedLevel}
              onSelectLevel={setSelectedLevel}
              onStatsUpdate={refreshStats}
              initialQuery={searchTriggerWord}
              onLogout={handleLogout}
              setActiveTab={setActiveTab}
              onNavigateToAdmin={handleNavigateToAdmin}
            />
          )}

          {activeTab === 'flashcards' && (
            <FlashcardView
              currentUser={currentUser}
              onSwitchToChat={() => setActiveTab('chat')}
              onStatsUpdate={refreshStats}
            />
          )}

          {activeTab === 'discover' && (
            <DiscoveryView
              onSelectWord={handleSelectWordFromDiscovery}
              onStatsUpdate={refreshStats}
            />
          )}

          {activeTab === 'admin' && (
            currentUser.role === 'admin' ? (
              <AdminPanel currentUser={currentUser} />
            ) : (
              <ChatView
                currentUser={currentUser}
                selectedLevel={selectedLevel}
                onSelectLevel={setSelectedLevel}
                onStatsUpdate={refreshStats}
                initialQuery={searchTriggerWord}
              />
            )
          )}
        </ErrorBoundary>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200/80 dark:border-white/10 bg-white/60 dark:bg-[#171717]/80 backdrop-blur-xs py-3.5 text-center text-xs text-slate-500 dark:text-zinc-400 font-medium">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="flex items-center space-x-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>Chatbox 2.0 Local-Only AI Engine</span>
            <span>•</span>
            <span>3,725 Cặp Từ Vựng Chuẩn CEFR A1–B2</span>
          </div>

          <div className="text-slate-400 dark:text-zinc-500">
            Hỗ trợ phát âm Web Speech API • Độc lập hoàn toàn với Cloud API bên ngoài
          </div>
        </div>
      </footer>

    </div>
  );
}
