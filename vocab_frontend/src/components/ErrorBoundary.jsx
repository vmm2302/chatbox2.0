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
          <div className="max-w-xl w-full bg-white rounded-3xl p-6 sm:p-8 border border-rose-200 shadow-xl space-y-5 text-center">
            <div className="w-16 h-16 rounded-2xl bg-rose-100 text-rose-600 flex items-center justify-center mx-auto shadow-inner">
              <AlertOctagon className="w-8 h-8" />
            </div>

            <div>
              <h2 className="text-xl font-black text-slate-900 tracking-tight">
                Đã xảy ra sự cố hiển thị giao diện
              </h2>
              <p className="text-xs sm:text-sm text-slate-600 mt-1.5 leading-relaxed">
                Hệ thống đã tự động ngăn chặn sự cố trang trắng. Dữ liệu của bạn vẫn an toàn trên máy chủ.
              </p>
            </div>

            {this.state.error && (
              <div className="text-left bg-slate-900 text-rose-300 p-3.5 rounded-2xl text-[11px] font-mono overflow-x-auto max-h-36">
                <b>Lỗi:</b> {this.state.error.toString()}
              </div>
            )}

            <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
              <button
                onClick={this.handleReset}
                className="flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs transition-all shadow-md cursor-pointer"
              >
                <RefreshCw className="w-4 h-4" />
                <span>Thử tải lại</span>
              </button>

              {this.props.onNavigateHome && (
                <button
                  onClick={this.props.onNavigateHome}
                  className="flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-emerald-50 hover:bg-emerald-100 text-emerald-800 font-bold text-xs border border-emerald-200 transition-all cursor-pointer"
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
