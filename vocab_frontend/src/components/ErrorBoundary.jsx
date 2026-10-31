import React from 'react';
import { AlertOctagon, RefreshCw, Home } from 'lucide-react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    this.setState({ errorInfo });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    if (this.props.onReset) {
      this.props.onReset();
    } else {
      window.location.reload();
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-[400px] flex items-center justify-center p-6">
          <div className="max-w-xl w-full bg-white dark:bg-[#212121] rounded-3xl p-6 sm:p-8 border border-rose-200 dark:border-rose-900/40 shadow-xl space-y-5 text-center transition-colors">
            <div className="w-16 h-16 rounded-2xl bg-rose-100 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400 flex items-center justify-center mx-auto shadow-inner">
              <AlertOctagon className="w-8 h-8" />
            </div>

            <div>
              <h2 className="text-xl font-black text-slate-900 dark:text-white tracking-tight">
                Đã xảy ra sự cố hiển thị giao diện
              </h2>
              <p className="text-xs sm:text-sm text-slate-600 dark:text-zinc-400 mt-1.5 leading-relaxed">
                Hệ thống đã tự động ngăn chặn sự cố trang trắng. Dữ liệu của bạn vẫn an toàn trên máy chủ.
              </p>
            </div>

            {this.state.error && (
              <div className="text-left bg-slate-900 dark:bg-[#171717] text-rose-300 dark:text-rose-400 p-3.5 rounded-2xl text-[11px] font-mono overflow-x-auto max-h-36 border border-transparent dark:border-rose-950/50">
                <b>Lỗi:</b> {this.state.error.toString()}
              </div>
            )}

            <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
              <button
                onClick={this.handleReset}
                className="flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 dark:bg-[#2f2f2f] dark:hover:bg-[#383838] dark:border dark:border-white/10 text-white font-bold text-xs transition-all shadow-md cursor-pointer"
              >
                <RefreshCw className="w-4 h-4" />
                <span>Thử tải lại</span>
              </button>

              {this.props.onNavigateHome && (
                <button
                  onClick={this.props.onNavigateHome}
                  className="flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 hover:bg-emerald-100 dark:hover:bg-emerald-900/40 text-emerald-800 dark:text-emerald-300 font-bold text-xs border border-emerald-200 dark:border-emerald-800/40 transition-all cursor-pointer"
                >
                  <Home className="w-4 h-4" />
                  <span>Về trang Tra cứu</span>
                </button>
              )}
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
