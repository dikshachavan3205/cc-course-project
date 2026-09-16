// Minimal render error boundary — a crash in any one view must not take the
// whole Q-Deck down. Falls back to a quiet, on-brand panel with the error
// message; the header, tab bar, and polling loop keep running, and switching
// tabs (a new key) resets the boundary.
import { Component } from 'react';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <section className="panel p-5" role="alert" aria-live="assertive">
          <p className="panel-label">render error</p>
          <p className="mt-2 text-sm text-primary">
            {this.state.error?.message || 'Something went wrong rendering this view.'}
          </p>
        </section>
      );
    }
    return this.props.children;
  }
}