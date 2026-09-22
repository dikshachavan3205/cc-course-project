import { Component } from "react";

export class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("[ChronoNet boundary]", error, info?.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="panel p-6">
          <p className="text-sm font-semibold text-primary">Something broke in this view</p>
          <p className="num mt-2 break-words text-xs text-muted">{String(this.state.error.message || this.state.error)}</p>
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            className="mt-4 rounded-sm border border-border-mid/40 bg-elevated px-3 py-1.5 text-xs text-primary hover:bg-surface"
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}