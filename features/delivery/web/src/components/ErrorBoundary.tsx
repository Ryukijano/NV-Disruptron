import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("NV Disruptron Error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-dvh flex-col items-center justify-center bg-obsidian px-4 text-text font-mono">
          <h1 className="text-crimson text-xl font-bold mb-4">RENDER FAILURE</h1>
          <pre className="text-xs text-muted max-w-xl whitespace-pre-wrap break-words bg-[#0d1117] p-4 rounded border border-crimson/30">
            {this.state.error?.message ?? "Unknown error"}
          </pre>
          <p className="text-[10px] text-muted mt-4 uppercase tracking-wider">
            Check browser console for full stack trace
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}
