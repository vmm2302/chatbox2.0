import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import ChatView from './components/ChatView';
import DiscoveryView from './components/DiscoveryView';
import AdminPanel from './components/AdminPanel';
import AuthPage from './components/AuthPage';
import ErrorBoundary from './components/ErrorBoundary';
import ThemeToggle from './components/ThemeToggle';
import { verifySession } from './services/api';
import { getInitialTheme, applyTheme, subscribeSystemTheme, THEME_STORAGE_KEY } from './utils/theme';

export default function App() {
  // Luôn bắt đầu ở trạng thái đăng xuất khi khởi chạy giao diện
  const [currentUser, setCurrentUser] = useState(null);
  const [isAdminPage, setIsAdminPage] = useState(false);
  const [activeTab, setActiveTab] = useState('chat');
  const [selectedLevel, setSelectedLevel] = useState('Tất cả');
  const [searchTriggerWord, setSearchTriggerWord] = useState('');
  const [themeMode, setThemeMode] = useState(getInitialTheme);

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

  const handleLogout = () => {
    setCurrentUser(null);
    setIsAdminPage(false);
    try {
      localStorage.removeItem('vocab_chat_user');
      sessionStorage.removeItem('vocab_chat_user');
    } catch (e) {
      console.error('Failed to clear storage:', e);
    }
    setActiveTab('chat');
    // Clear URL query parameters so the address bar cleanly returns to /
    clearAdminQueryParam();
  };

  // Khi giao diện được khởi chạy hoặc tải lại: xóa sạch phiên lưu cũ để luôn luôn đăng xuất
  useEffect(() => {
    try {
      localStorage.removeItem('vocab_chat_user');
      sessionStorage.removeItem('vocab_chat_user');
    } catch (e) {}
    clearAdminQueryParam();
  }, []);

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

  useEffect(() => {
    if (currentUser?.id) {
      verifySession(currentUser.id).then((res) => {
        if (!res) {
          handleLogout();
        }
      }).catch(() => {});
    }
  }, [currentUser]);

  const handleLoginSuccess = (user) => {
    setCurrentUser(user);
    // Không lưu vĩnh viễn vào localStorage để khi chạy lại giao diện luôn luôn bắt đầu ở trang đăng nhập
    try {
      localStorage.removeItem('vocab_chat_user');
      sessionStorage.removeItem('vocab_chat_user');
    } catch (e) {}
    // If the logged-in user is not an admin, ensure they never land on ?page=admin
    if (user?.role !== 'admin') {
      setIsAdminPage(false);
      clearAdminQueryParam();
    }
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
          <div className="w-full px-3 sm:px-6">
            <div className="flex items-center justify-between gap-2 sm:gap-3 h-14 sm:h-16">
              {/* Admin Brand */}
              <div className="flex items-center space-x-2.5 sm:space-x-3 shrink-0">
                <div className="w-9 h-9 sm:w-11 sm:h-11 rounded-2xl bg-gradient-to-tr from-indigo-600 via-purple-600 to-indigo-700 flex items-center justify-center shadow-md shadow-indigo-500/20 text-white font-black text-lg sm:text-xl shrink-0">
                  🛡️
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-lg sm:text-xl font-black tracking-tight text-slate-900 dark:text-white whitespace-nowrap">
                      Vocab<span className="text-indigo-600 dark:text-indigo-400">Admin</span>
                    </span>
                    <span className="hidden sm:inline-flex px-2 py-0.5 text-[10px] sm:text-[11px] font-bold uppercase tracking-wider rounded-full bg-indigo-100 dark:bg-indigo-950/70 text-indigo-800 dark:text-indigo-300 border border-indigo-200/60 dark:border-indigo-800/60 whitespace-nowrap">
                      Portal Quản Trị
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-zinc-400 font-medium hidden xl:block">
                    Hệ thống quản trị tài khoản, cơ sở tri thức & giám sát AI trung tâm
                  </p>
                </div>
              </div>

              {/* Admin Actions */}
              <div className="flex items-center space-x-1.5 sm:space-x-2.5 shrink-0">
                <button
                  onClick={handleNavigateToHome}
                  className="flex items-center space-x-1 sm:space-x-1.5 px-2.5 sm:px-3.5 py-1.5 rounded-xl bg-slate-100 dark:bg-[#262626] hover:bg-slate-200 dark:hover:bg-[#2f2f2f] text-slate-700 dark:text-[#ececec] text-xs sm:text-sm font-bold transition-all cursor-pointer border border-slate-200 dark:border-white/10 shrink-0 whitespace-nowrap"
                  title="Quay lại ứng dụng tra cứu từ vựng"
                >
                  <span>←</span>
                  <span className="hidden sm:inline">Quay lại</span>
                  <span className="hidden md:inline">ứng dụng chính</span>
                </button>

                {/* Theme Toggle in Admin Portal */}
                <ThemeToggle themeMode={themeMode} onThemeChange={handleThemeChange} />

                <div className="hidden lg:flex items-center space-x-2 bg-slate-50 dark:bg-[#212121] px-2.5 py-1 rounded-2xl border border-slate-200 dark:border-white/10 shrink-0">
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
                  className="p-1.5 sm:px-3 sm:py-1.5 rounded-xl text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 border border-transparent hover:border-rose-200 dark:hover:border-rose-900/40 text-xs font-bold transition-all cursor-pointer flex items-center space-x-1 shrink-0 whitespace-nowrap"
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
      
      {/* Main App Navigation Bar */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
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
              initialQuery={searchTriggerWord}
              onLogout={handleLogout}
              setActiveTab={setActiveTab}
              onNavigateToAdmin={handleNavigateToAdmin}
            />
          )}

          {activeTab === 'discover' && (
            <DiscoveryView
              onSelectWord={handleSelectWordFromDiscovery}
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
                initialQuery={searchTriggerWord}
              />
            )
          )}
        </ErrorBoundary>
      </main>

    </div>
  );
}
