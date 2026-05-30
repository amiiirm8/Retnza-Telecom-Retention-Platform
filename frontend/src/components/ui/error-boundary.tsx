"use client";

import { Component } from "react";
import { Card } from "@/components/ui/card";

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  section?: string;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback !== undefined) {
        return this.props.fallback;
      }
      return (
        <Card className="border-amber-200 bg-gradient-to-br from-amber-50 to-white p-6">
          <div className="flex flex-col items-center gap-3 text-center">
            <span className="text-2xl">⚠</span>
            <p className="text-sm font-medium text-slate-700">
              {this.props.section || "This section"} is temporarily unavailable
            </p>
            <p className="text-xs text-slate-500 leading-relaxed max-w-sm">
              The data could not be loaded. This may be a temporary issue — please try again.
            </p>
            <button
              onClick={() => this.setState({ hasError: false })}
              className="rounded-lg bg-indigo-600 px-4 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-500"
            >
              Retry
            </button>
          </div>
        </Card>
      );
    }
    return this.props.children;
  }
}
