import { Component, type ErrorInfo, type ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  errorMessage: string;
}

/** Bọc toàn bộ ứng dụng để bắt lỗi giao diện và hiển thị nút tải lại thân thiện. */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  public state: ErrorBoundaryState = {
    hasError: false,
    errorMessage: '',
  };

  public static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return {
      hasError: true,
      errorMessage: error.message || 'Đã xảy ra sự cố hiển thị không mong muốn.',
    };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('[DEBUG][ErrorBoundary] Giao diện gặp lỗi:', error, errorInfo);
  }

  public render(): ReactNode {
    if (this.state.hasError) {
      return (
        <main className="flex min-h-screen items-center justify-center bg-slate-950 p-6 text-slate-100">
          <section className="max-w-md rounded-2xl border border-rose-800/60 bg-slate-900 p-6 text-center shadow-xl">
            <h1 className="text-xl font-bold text-rose-400">Không thể hiển thị giao diện</h1>
            <p className="mt-2 text-sm text-slate-300">
              Hệ thống gặp sự cố tạm thời khi dựng trang. Vui lòng tải lại để tiếp tục kiểm thử.
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-5 rounded-xl bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-400 focus:ring-2 focus:ring-emerald-300 focus:outline-none"
            >
              Tải lại trang
            </button>
          </section>
        </main>
      );
    }
    return this.props.children;
  }
}
