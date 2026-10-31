import React, { useState } from 'react';
import { Lock, User, Sparkles, BookOpen, ShieldCheck, ArrowRight, CheckCircle2, AlertCircle } from 'lucide-react';
import { loginUser, registerUser } from '../services/api';
import ThemeToggle from './ThemeToggle';

export default function AuthPage({ onLoginSuccess, themeMode, onThemeChange }) {
  const [tab, setTab] = useState('login'); // 'login' | 'register'
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setNotice('');
    setIsLoading(true);

    try {
      const res = await loginUser(username.trim(), password);
      onLoginSuccess(res.user);
    } catch (err) {
      setError(err.message || 'Đăng nhập không thành công.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    setNotice('');
    setIsLoading(true);

    try {
      const res = await registerUser(username.trim(), password, confirmPassword, displayName.trim());
      setNotice('Đăng ký thành công! Bạn có thể đăng nhập ngay.');
      setTab('login');
      setPassword('');
      setConfirmPassword('');
    } catch (err) {
      setError(err.message || 'Đăng ký không thành công.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 dark:bg-[#171717] flex items-center justify-center p-4 sm:p-6 text-slate-900 dark:text-[#ececec] relative transition-colors duration-200">
      
      {/* Floating Theme Toggle (Top Right) */}
      {onThemeChange && (
        <div className="absolute top-4 right-4 z-20">
          <ThemeToggle currentTheme={themeMode} onThemeChange={onThemeChange} />
        </div>
      )}

      {/* Container Box */}
      <div className="w-full max-w-5xl bg-white dark:bg-[#212121] rounded-3xl border border-slate-200 dark:border-white/10 shadow-2xl overflow-hidden grid grid-cols-1 lg:grid-cols-12">
        
        {/* Left Hero Banner */}
        <div className="lg:col-span-6 p-8 sm:p-12 flex flex-col justify-between bg-gradient-to-br from-emerald-600/90 via-teal-700/80 to-cyan-800/90 text-white relative overflow-hidden">
          <div className="absolute -top-20 -left-20 w-64 h-64 bg-emerald-400/20 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute -bottom-20 -right-20 w-64 h-64 bg-cyan-400/20 rounded-full blur-3xl pointer-events-none" />

          <div>
            <div className="flex items-center space-x-3 mb-6">
              <div className="w-12 h-12 rounded-2xl bg-white/20 backdrop-blur-md flex items-center justify-center text-2xl shadow-inner">
                📚
              </div>
              <div>
                <h1 className="text-2xl font-black tracking-tight">VocabChat 2.0</h1>
                <p className="text-xs font-semibold text-emerald-200 uppercase tracking-wider">
                  Trợ lý từ vựng tiếng Anh CEFR
                </p>
              </div>
            </div>

            <div className="space-y-4 my-8">
              <h2 className="text-3xl sm:text-4xl font-black leading-tight">
                Mỗi từ mới,<br />
                <span className="text-emerald-300">một bước tiến gần hơn.</span>
              </h2>
              <p className="text-sm sm:text-base text-emerald-100/90 leading-relaxed max-w-md">
                Tra cứu từ vựng chuẩn Oxford 3,000 từ A1 đến B2, phân biệt từ dễ nhầm lẫn, nghe phát âm bản ngữ và ôn tập qua thẻ lật 3D.
              </p>
            </div>
          </div>

          <div className="space-y-3 pt-6 border-t border-white/20 text-xs text-emerald-100/80">
            <div className="flex items-center space-x-2">
              <ShieldCheck className="w-4 h-4 text-emerald-300 shrink-0" />
              <span>Xử lý 100% Cục bộ — An toàn và bảo mật dữ liệu tuyệt đối</span>
            </div>
            <div className="flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-emerald-300 shrink-0" />
              <span>Hỗ trợ chuẩn 4 cấp độ CEFR: A1 · A2 · B1 · B2</span>
            </div>
          </div>
        </div>

        {/* Right Auth Forms */}
        <div className="lg:col-span-6 p-8 sm:p-12 bg-white dark:bg-[#1a1a1a] flex flex-col justify-center text-slate-800 dark:text-[#ececec]">
          
          {/* Tabs */}
          <div className="flex items-center space-x-2 bg-slate-100 dark:bg-[#262626] p-1.5 rounded-2xl mb-6 border border-transparent dark:border-white/5">
            <button
              onClick={() => { setTab('login'); setError(''); setNotice(''); }}
              className={`flex-1 py-2.5 rounded-xl text-xs sm:text-sm font-extrabold transition-all cursor-pointer ${
                tab === 'login'
                  ? 'bg-white dark:bg-[#2f2f2f] text-emerald-700 dark:text-emerald-400 shadow-sm dark:border dark:border-white/10'
                  : 'text-slate-500 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-200'
              }`}
            >
              🔐 Đăng nhập
            </button>
            <button
              onClick={() => { setTab('register'); setError(''); setNotice(''); }}
              className={`flex-1 py-2.5 rounded-xl text-xs sm:text-sm font-extrabold transition-all cursor-pointer ${
                tab === 'register'
                  ? 'bg-white dark:bg-[#2f2f2f] text-emerald-700 dark:text-emerald-400 shadow-sm dark:border dark:border-white/10'
                  : 'text-slate-500 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-200'
              }`}
            >
              📝 Tạo tài khoản mới
            </button>
          </div>

          {/* Heading */}
          <div className="mb-6">
            <h3 className="text-xl sm:text-2xl font-black text-slate-900 dark:text-white">
              {tab === 'login' ? 'Chào mừng bạn trở lại 👋' : 'Bắt đầu học ngay hôm nay ✨'}
            </h3>
            <p className="text-xs sm:text-sm text-slate-500 dark:text-zinc-400 mt-1">
              {tab === 'login'
                ? 'Đăng nhập để tiếp tục buổi học và xem lịch sử tra cứu của bạn.'
                : 'Tạo tài khoản để cá nhân hóa sổ tay từ vựng và lưu tiến độ ôn tập.'}
            </p>
          </div>

          {/* Notices & Errors */}
          {error && (
            <div className="flex items-center space-x-2 p-3.5 mb-4 rounded-xl bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-900/40 text-xs sm:text-sm font-semibold">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          {notice && (
            <div className="flex items-center space-x-2 p-3.5 mb-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-900/40 text-xs sm:text-sm font-semibold">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{notice}</span>
            </div>
          )}

          {/* LOGIN FORM */}
          {tab === 'login' ? (
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1.5">
                  Tên đăng nhập
                </label>
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="ví dụ: admin hoặc nguyenvana"
                  className="w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-[#262626] text-slate-800 dark:text-[#ececec] placeholder:text-slate-400 dark:placeholder:text-zinc-500 focus:border-emerald-500 dark:focus:border-emerald-400 focus:ring-4 focus:ring-emerald-500/10 text-sm font-semibold focus:outline-hidden transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1.5">
                  Mật khẩu
                </label>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Nhập mật khẩu"
                  className="w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-[#262626] text-slate-800 dark:text-[#ececec] placeholder:text-slate-400 dark:placeholder:text-zinc-500 focus:border-emerald-500 dark:focus:border-emerald-400 focus:ring-4 focus:ring-emerald-500/10 text-sm font-semibold focus:outline-hidden transition-all"
                />
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-3.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white font-black text-sm shadow-md shadow-emerald-500/25 active:scale-98 transition-all disabled:opacity-50 cursor-pointer flex items-center justify-center space-x-2 mt-2"
              >
                <span>{isLoading ? 'Đang xác thực...' : 'Đăng nhập vào học'}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>
          ) : (
            /* REGISTER FORM */
            <form onSubmit={handleRegister} className="space-y-3.5">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                  Tên đăng nhập *
                </label>
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="3–30 ký tự (chữ cái, số)"
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-[#262626] text-slate-800 dark:text-[#ececec] placeholder:text-slate-400 dark:placeholder:text-zinc-500 focus:border-emerald-500 dark:focus:border-emerald-400 focus:ring-4 focus:ring-emerald-500/10 text-sm font-semibold focus:outline-hidden transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                  Tên hiển thị
                </label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Ví dụ: Minh Anh"
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-[#262626] text-slate-800 dark:text-[#ececec] placeholder:text-slate-400 dark:placeholder:text-zinc-500 focus:border-emerald-500 dark:focus:border-emerald-400 focus:ring-4 focus:ring-emerald-500/10 text-sm font-semibold focus:outline-hidden transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                  Mật khẩu *
                </label>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Tối thiểu 6 ký tự"
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-[#262626] text-slate-800 dark:text-[#ececec] placeholder:text-slate-400 dark:placeholder:text-zinc-500 focus:border-emerald-500 dark:focus:border-emerald-400 focus:ring-4 focus:ring-emerald-500/10 text-sm font-semibold focus:outline-hidden transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                  Xác nhận mật khẩu *
                </label>
                <input
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Nhập lại mật khẩu"
                  className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-[#262626] text-slate-800 dark:text-[#ececec] placeholder:text-slate-400 dark:placeholder:text-zinc-500 focus:border-emerald-500 dark:focus:border-emerald-400 focus:ring-4 focus:ring-emerald-500/10 text-sm font-semibold focus:outline-hidden transition-all"
                />
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-3.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white font-black text-sm shadow-md shadow-emerald-500/25 active:scale-98 transition-all disabled:opacity-50 cursor-pointer flex items-center justify-center space-x-2 mt-2"
              >
                <span>{isLoading ? 'Đang tạo...' : 'Tạo tài khoản'}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>
          )}

        </div>

      </div>
    </div>
  );
}
