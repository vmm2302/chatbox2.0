import React, { useState } from 'react';
import {
  Sparkles,
  ShieldCheck,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  Eye,
  EyeOff,
  User,
  Lock,
  KeyRound,
  GraduationCap,
  BookOpen,
  Zap,
  Check,
  Loader2
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { loginUser, registerUser } from '../services/api';
import ThemeToggle from './ThemeToggle';

export default function AuthPage({ onLoginSuccess, themeMode, onThemeChange }) {
  const [tab, setTab] = useState('login'); // 'login' | 'register'

  // State form Đăng nhập
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);

  // State form Đăng ký
  const [registerUsername, setRegisterUsername] = useState('');
  const [registerDisplayName, setRegisterDisplayName] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [registerConfirmPassword, setRegisterConfirmPassword] = useState('');
  const [showRegisterPassword, setShowRegisterPassword] = useState(false);
  const [showRegisterConfirmPassword, setShowRegisterConfirmPassword] = useState(false);

  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isShaking, setIsShaking] = useState(false);

  const triggerShake = () => {
    setIsShaking(true);
    setTimeout(() => setIsShaking(false), 500);
  };

  const handleSwitchTab = (newTab) => {
    setTab(newTab);
    setError('');
    setNotice('');
  };

  // Tính toán độ mạnh mật khẩu đăng ký
  const getPasswordStrength = (pass) => {
    if (!pass) return { score: 0, label: '', color: '', width: '0%' };
    let score = 0;
    if (pass.length >= 6) score += 1;
    if (pass.length >= 8) score += 1;
    if (/[0-9]/.test(pass) && /[a-zA-Z]/.test(pass)) score += 1;
    if (/[^a-zA-Z0-9]/.test(pass)) score += 1;

    if (score <= 1) {
      return { score: 1, label: 'Yếu (Cần ít nhất 6 ký tự)', color: 'bg-rose-500', width: '33%' };
    } else if (score <= 2) {
      return { score: 2, label: 'Trung bình (Nên thêm số và chữ cái)', color: 'bg-amber-500', width: '66%' };
    } else {
      return { score: 3, label: 'Mạnh & An toàn tuyệt đối', color: 'bg-emerald-500', width: '100%' };
    }
  };

  const passwordStrength = getPasswordStrength(registerPassword);
  const isPasswordMatch =
    registerConfirmPassword && registerPassword === registerConfirmPassword;
  const isPasswordMismatch =
    registerConfirmPassword && registerPassword !== registerConfirmPassword;

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setNotice('');
    setIsLoading(true);

    try {
      const res = await loginUser(loginUsername.trim(), loginPassword);
      onLoginSuccess(res.user);
    } catch (err) {
      setError(err.message || 'Đăng nhập không thành công. Vui lòng kiểm tra lại tài khoản hoặc mật khẩu.');
      triggerShake();
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    setNotice('');

    if (registerPassword !== registerConfirmPassword) {
      setError('Mật khẩu và xác nhận mật khẩu không trùng khớp!');
      triggerShake();
      return;
    }

    setIsLoading(true);

    try {
      await registerUser(
        registerUsername.trim(),
        registerPassword,
        registerConfirmPassword,
        registerDisplayName.trim()
      );
      
      // Hiệu ứng pháo giấy ăn mừng đăng ký thành công
      try {
        confetti({
          particleCount: 80,
          spread: 70,
          origin: { y: 0.6 }
        });
      } catch {
        // Fallback im lặng nếu canvas không khả dụng
      }

      setNotice('🎉 Đăng ký thành công! Bạn có thể đăng nhập để bắt đầu học ngay.');
      setTab('login');
      // Điền sẵn tên đăng nhập vừa tạo
      setLoginUsername(registerUsername.trim());
      setLoginPassword('');
      // Xóa form đăng ký
      setRegisterUsername('');
      setRegisterDisplayName('');
      setRegisterPassword('');
      setRegisterConfirmPassword('');
    } catch (err) {
      setError(err.message || 'Đăng ký tài khoản không thành công.');
      triggerShake();
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 dark:bg-[#141414] flex items-center justify-center p-3 sm:p-6 text-slate-900 dark:text-[#ececec] relative overflow-hidden transition-colors duration-300">
      
      {/* Dynamic Ambient Background Glows */}
      <div className="absolute -top-32 -left-32 w-96 h-96 bg-emerald-500/15 dark:bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-32 -right-32 w-96 h-96 bg-teal-500/15 dark:bg-teal-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-cyan-500/10 dark:bg-cyan-500/5 rounded-full blur-3xl pointer-events-none" />

      {/* Floating Theme Toggle (Top Right) */}
      {onThemeChange && (
        <div className="absolute top-4 right-4 z-30">
          <div className="p-1 rounded-2xl bg-white/70 dark:bg-[#212121]/80 backdrop-blur-md border border-slate-200/80 dark:border-white/10 shadow-md">
            <ThemeToggle themeMode={themeMode} onThemeChange={onThemeChange} />
          </div>
        </div>
      )}

      {/* Main Container Card */}
      <div
        className={`w-full max-w-5xl bg-white/95 dark:bg-[#1e1e1e]/95 backdrop-blur-xl rounded-3xl border border-slate-200/80 dark:border-white/10 shadow-[0_25px_60px_-15px_rgba(0,0,0,0.18)] dark:shadow-[0_25px_60px_-15px_rgba(0,0,0,0.6)] overflow-hidden grid grid-cols-1 lg:grid-cols-12 relative z-10 transition-all duration-300 ${
          isShaking ? 'animate-shake' : ''
        }`}
      >
        
        {/* Left Hero Section */}
        <div className="lg:col-span-6 p-6 sm:p-10 lg:p-12 flex flex-col justify-between bg-gradient-to-br from-emerald-600 via-teal-700 to-cyan-800 text-white relative overflow-hidden select-none">
          {/* Subtle Ambient Orb inside Banner */}
          <div className="absolute -top-16 -left-16 w-56 h-56 bg-emerald-300/20 rounded-full blur-2xl pointer-events-none" />
          <div className="absolute -bottom-16 -right-16 w-56 h-56 bg-cyan-300/20 rounded-full blur-2xl pointer-events-none" />

          {/* Top Brand Header */}
          <div className="relative z-10">
            <div className="flex items-center space-x-3 mb-6">
              <div className="w-12 h-12 rounded-2xl bg-white/20 backdrop-blur-md flex items-center justify-center text-2xl shadow-inner border border-white/20">
                📚
              </div>
              <div>
                <h1 className="text-xl sm:text-2xl font-black tracking-tight leading-tight">
                  Chatbot Từ Vựng Tiếng Anh
                </h1>
                <div className="flex items-center space-x-1.5 mt-0.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-300 animate-ping" />
                  <p className="text-[11px] font-bold text-emerald-100 uppercase tracking-wider">
                    Trợ lý học từ vựng thông minh
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-3 my-6 sm:my-8">
              <h2 className="text-2xl sm:text-4xl font-black leading-tight tracking-tight">
                Mỗi từ mới,<br />
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-200 via-teal-100 to-cyan-200">
                  một bước tiến gần hơn.
                </span>
              </h2>
              <p className="text-xs sm:text-sm text-emerald-50/90 leading-relaxed max-w-md font-medium">
                Tra cứu từ vựng chuẩn xác, phát âm bản xứ tự nhiên, phân tích ngữ cảnh thực tế và lưu trữ tiến độ học tập thông minh.
              </p>
            </div>

            {/* Floating Vocabulary Interactive Cards Showcase */}
            <div className="space-y-2.5 my-6 sm:my-8 relative">
              {/* Card 1: amazing */}
              <div className="animate-float-slow bg-white/15 hover:bg-white/20 transition-all backdrop-blur-md border border-white/25 rounded-2xl p-3 shadow-lg flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-8 h-8 rounded-xl bg-emerald-400/30 flex items-center justify-center text-emerald-200 font-bold text-xs">
                    ⭐
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-extrabold text-sm tracking-wide">amazing</span>
                      <span className="text-xs text-emerald-200 font-mono">/əˈmeɪzɪŋ/</span>
                    </div>
                    <p className="text-[11px] text-emerald-100/90 font-medium">Tuyệt vời, kinh ngạc, phi thường</p>
                  </div>
                </div>
                <Sparkles className="w-4 h-4 text-emerald-200 shrink-0" />
              </div>

              {/* Card 2: discover */}
              <div className="animate-float-reverse bg-white/15 hover:bg-white/20 transition-all backdrop-blur-md border border-white/25 rounded-2xl p-3 shadow-lg flex items-center justify-between sm:ml-4">
                <div className="flex items-center space-x-3">
                  <div className="w-8 h-8 rounded-xl bg-teal-400/30 flex items-center justify-center text-teal-200 font-bold text-xs">
                    🚀
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-extrabold text-sm tracking-wide">discover</span>
                      <span className="text-xs text-teal-200 font-mono">/dɪˈskʌvə(r)/</span>
                    </div>
                    <p className="text-[11px] text-teal-100/90 font-medium">Khám phá, tìm ra, phát hiện ra</p>
                  </div>
                </div>
                <BookOpen className="w-4 h-4 text-teal-200 shrink-0" />
              </div>

              {/* Card 3: brilliant */}
              <div className="animate-float-delayed hidden sm:flex bg-white/15 hover:bg-white/20 transition-all backdrop-blur-md border border-white/25 rounded-2xl p-3 shadow-lg items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-8 h-8 rounded-xl bg-cyan-400/30 flex items-center justify-center text-cyan-200 font-bold text-xs">
                    💡
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-extrabold text-sm tracking-wide">brilliant</span>
                      <span className="text-xs text-cyan-200 font-mono">/ˈbrɪliənt/</span>
                    </div>
                    <p className="text-[11px] text-cyan-100/90 font-medium">Sáng dạ, tài giỏi, xuất sắc, rực rỡ</p>
                  </div>
                </div>
                <Zap className="w-4 h-4 text-cyan-200 shrink-0" />
              </div>
            </div>
          </div>

          {/* Bottom Security Footer */}
          <div className="pt-4 border-t border-white/20 relative z-10">
            <div className="flex items-center space-x-2 text-xs text-emerald-100/90 font-medium">
              <ShieldCheck className="w-4 h-4 text-emerald-300 shrink-0" />
              <span>Xử lý 100% Cục bộ — An toàn và bảo mật dữ liệu</span>
            </div>
          </div>
        </div>

        {/* Right Auth Forms Section */}
        <div className="lg:col-span-6 p-6 sm:p-10 lg:p-12 bg-white dark:bg-[#1a1a1a] flex flex-col justify-center text-slate-800 dark:text-[#ececec]">
          
          {/* Segmented Switch Tabs */}
          <div className="flex items-center space-x-2 bg-slate-100 dark:bg-[#262626] p-1.5 rounded-2xl mb-5 border border-slate-200/60 dark:border-white/5">
            <button
              type="button"
              onClick={() => handleSwitchTab('login')}
              className={`flex-1 py-2.5 rounded-xl text-xs sm:text-sm font-extrabold transition-all duration-200 cursor-pointer flex items-center justify-center space-x-1.5 ${
                tab === 'login'
                  ? 'bg-white dark:bg-[#333333] text-emerald-600 dark:text-emerald-400 shadow-sm border border-slate-200/50 dark:border-white/10'
                  : 'text-slate-500 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-200'
              }`}
            >
              <Lock className="w-3.5 h-3.5" />
              <span>Đăng nhập</span>
            </button>
            <button
              type="button"
              onClick={() => handleSwitchTab('register')}
              className={`flex-1 py-2.5 rounded-xl text-xs sm:text-sm font-extrabold transition-all duration-200 cursor-pointer flex items-center justify-center space-x-1.5 ${
                tab === 'register'
                  ? 'bg-white dark:bg-[#333333] text-emerald-600 dark:text-emerald-400 shadow-sm border border-slate-200/50 dark:border-white/10'
                  : 'text-slate-500 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-200'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Tạo tài khoản mới</span>
            </button>
          </div>

          {/* Heading */}
          <div className="mb-5">
            <h3 className="text-xl sm:text-2xl font-black text-slate-900 dark:text-white">
              {tab === 'login' ? 'Chào mừng bạn trở lại 👋' : 'Bắt đầu hành trình học tập ✨'}
            </h3>
            <p className="text-xs sm:text-sm text-slate-500 dark:text-zinc-400 mt-1 font-medium">
              {tab === 'login'
                ? 'Đăng nhập để tiếp tục buổi học và quản lý sổ từ vựng cá nhân.'
                : 'Tạo tài khoản để cá nhân hóa từ vựng và lưu trữ lịch sử tương tác.'}
            </p>
          </div>

          {/* Notifications & Error Alerts */}
          {error && (
            <div className="flex items-center space-x-2.5 p-3.5 mb-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-400 border border-rose-200 dark:border-rose-900/40 text-xs sm:text-sm font-semibold shadow-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          {notice && (
            <div className="flex items-center space-x-2.5 p-3.5 mb-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-900/40 text-xs sm:text-sm font-semibold shadow-xs">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{notice}</span>
            </div>
          )}

          {/* LOGIN FORM */}
          {tab === 'login' ? (
            <form onSubmit={handleLogin} className="space-y-4">
              {/* Username Input */}
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1.5">
                  Tên đăng nhập
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400 dark:text-zinc-500">
                    <User className="w-4 h-4" />
                  </div>
                  <input
                    type="text"
                    required
                    value={loginUsername}
                    onChange={(e) => setLoginUsername(e.target.value)}
                    placeholder="ví dụ: admin hoặc nguyenvana"
                    className="w-full pl-10 pr-4 py-3 rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50/50 dark:bg-[#242424] text-slate-800 dark:text-[#ececec] placeholder:text-slate-400 dark:placeholder:text-zinc-500 focus:bg-white dark:focus:bg-[#2a2a2a] focus:border-emerald-500 dark:focus:border-emerald-400 focus:ring-4 focus:ring-emerald-500/15 text-sm font-semibold focus:outline-hidden transition-all"
                  />
                </div>
              </div>

              {/* Password Input */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400">
                    Mật khẩu
                  </label>
                </div>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400 dark:text-zinc-500">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type={showLoginPassword ? 'text' : 'password'}
                    required
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    placeholder="Nhập mật khẩu của bạn"
                    className="w-full pl-10 pr-11 py-3 rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50/50 dark:bg-[#242424] text-slate-800 dark:text-[#ececec] placeholder:text-slate-400 dark:placeholder:text-zinc-500 focus:bg-white dark:focus:bg-[#2a2a2a] focus:border-emerald-500 dark:focus:border-emerald-400 focus:ring-4 focus:ring-emerald-500/15 text-sm font-semibold focus:outline-hidden transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowLoginPassword(!showLoginPassword)}
                    className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 dark:text-zinc-500 dark:hover:text-zinc-300 transition-colors cursor-pointer"
                    title={showLoginPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                  >
                    {showLoginPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Remember Me Option */}
              <div className="flex items-center justify-between text-xs pt-1">
                <label className="flex items-center space-x-2 text-slate-600 dark:text-zinc-400 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="w-4 h-4 rounded text-emerald-600 focus:ring-emerald-500 border-slate-300 dark:border-zinc-600 dark:bg-zinc-800 cursor-pointer"
                  />
                  <span className="font-semibold">Ghi nhớ thông tin đăng nhập</span>
                </label>
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-3.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white font-black text-sm shadow-lg shadow-emerald-500/25 active:scale-[0.98] transition-all disabled:opacity-50 cursor-pointer flex items-center justify-center space-x-2 mt-3 animate-shimmer"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Đang xác thực hệ thống...</span>
                  </>
                ) : (
                  <>
                    <span>Đăng nhập vào học</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>
          ) : (
            /* REGISTER FORM */
            <form onSubmit={handleRegister} className="space-y-3.5">
              {/* Username Input */}
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                  Tên đăng nhập *
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400 dark:text-zinc-500">
                    <User className="w-4 h-4" />
                  </div>
                  <input
                    type="text"
                    required
                    value={registerUsername}
                    onChange={(e) => setRegisterUsername(e.target.value)}
                    placeholder="3–30 ký tự (chữ cái, số)"
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50/50 dark:bg-[#242424] text-slate-800 dark:text-[#ececec] placeholder:text-slate-400 dark:placeholder:text-zinc-500 focus:bg-white dark:focus:bg-[#2a2a2a] focus:border-emerald-500 dark:focus:border-emerald-400 focus:ring-4 focus:ring-emerald-500/15 text-sm font-semibold focus:outline-hidden transition-all"
                  />
                </div>
              </div>

              {/* Display Name Input */}
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                  Tên hiển thị (biệt danh)
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400 dark:text-zinc-500">
                    <GraduationCap className="w-4 h-4" />
                  </div>
                  <input
                    type="text"
                    value={registerDisplayName}
                    onChange={(e) => setRegisterDisplayName(e.target.value)}
                    placeholder="Ví dụ: Minh Anh"
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50/50 dark:bg-[#242424] text-slate-800 dark:text-[#ececec] placeholder:text-slate-400 dark:placeholder:text-zinc-500 focus:bg-white dark:focus:bg-[#2a2a2a] focus:border-emerald-500 dark:focus:border-emerald-400 focus:ring-4 focus:ring-emerald-500/15 text-sm font-semibold focus:outline-hidden transition-all"
                  />
                </div>
              </div>

              {/* Password Input */}
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                  Mật khẩu *
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400 dark:text-zinc-500">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type={showRegisterPassword ? 'text' : 'password'}
                    required
                    value={registerPassword}
                    onChange={(e) => setRegisterPassword(e.target.value)}
                    placeholder="Tối thiểu 6 ký tự"
                    className="w-full pl-10 pr-11 py-2.5 rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50/50 dark:bg-[#242424] text-slate-800 dark:text-[#ececec] placeholder:text-slate-400 dark:placeholder:text-zinc-500 focus:bg-white dark:focus:bg-[#2a2a2a] focus:border-emerald-500 dark:focus:border-emerald-400 focus:ring-4 focus:ring-emerald-500/15 text-sm font-semibold focus:outline-hidden transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowRegisterPassword(!showRegisterPassword)}
                    className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 dark:text-zinc-500 dark:hover:text-zinc-300 transition-colors cursor-pointer"
                    title={showRegisterPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                  >
                    {showRegisterPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>

                {/* Password Strength Indicator */}
                {registerPassword && (
                  <div className="mt-1.5 space-y-1">
                    <div className="h-1.5 w-full bg-slate-100 dark:bg-[#333333] rounded-full overflow-hidden">
                      <div
                        className={`h-full transition-all duration-300 ${passwordStrength.color}`}
                        style={{ width: passwordStrength.width }}
                      />
                    </div>
                    <div className="flex items-center justify-between text-[11px] font-semibold text-slate-500 dark:text-zinc-400">
                      <span>Độ an toàn:</span>
                      <span className={passwordStrength.score >= 3 ? 'text-emerald-500 font-bold' : passwordStrength.score === 2 ? 'text-amber-500 font-bold' : 'text-rose-500 font-bold'}>
                        {passwordStrength.label}
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* Confirm Password Input */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400">
                    Xác nhận mật khẩu *
                  </label>
                  {isPasswordMatch && (
                    <span className="flex items-center space-x-1 text-[11px] font-bold text-emerald-600 dark:text-emerald-400">
                      <Check className="w-3 h-3" />
                      <span>Trùng khớp</span>
                    </span>
                  )}
                  {isPasswordMismatch && (
                    <span className="text-[11px] font-bold text-rose-500">
                      Chưa khớp
                    </span>
                  )}
                </div>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400 dark:text-zinc-500">
                    <KeyRound className="w-4 h-4" />
                  </div>
                  <input
                    type={showRegisterConfirmPassword ? 'text' : 'password'}
                    required
                    value={registerConfirmPassword}
                    onChange={(e) => setRegisterConfirmPassword(e.target.value)}
                    placeholder="Nhập lại mật khẩu vừa tạo"
                    className={`w-full pl-10 pr-11 py-2.5 rounded-xl border bg-slate-50/50 dark:bg-[#242424] text-slate-800 dark:text-[#ececec] placeholder:text-slate-400 dark:placeholder:text-zinc-500 focus:bg-white dark:focus:bg-[#2a2a2a] text-sm font-semibold focus:outline-hidden transition-all ${
                      isPasswordMatch
                        ? 'border-emerald-500 dark:border-emerald-500/80 focus:ring-4 focus:ring-emerald-500/15'
                        : isPasswordMismatch
                        ? 'border-rose-400 dark:border-rose-500 focus:ring-4 focus:ring-rose-500/15'
                        : 'border-slate-200 dark:border-white/10 focus:border-emerald-500 dark:focus:border-emerald-400 focus:ring-4 focus:ring-emerald-500/15'
                    }`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowRegisterConfirmPassword(!showRegisterConfirmPassword)}
                    className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 dark:text-zinc-500 dark:hover:text-zinc-300 transition-colors cursor-pointer"
                    title={showRegisterConfirmPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                  >
                    {showRegisterConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-3.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white font-black text-sm shadow-lg shadow-emerald-500/25 active:scale-[0.98] transition-all disabled:opacity-50 cursor-pointer flex items-center justify-center space-x-2 mt-3 animate-shimmer"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Đang khởi tạo tài khoản...</span>
                  </>
                ) : (
                  <>
                    <span>Tạo tài khoản học tập</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>
          )}

        </div>

      </div>
    </div>
  );
}
