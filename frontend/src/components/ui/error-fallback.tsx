"use client";

interface ErrorFallbackProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

export function ErrorFallback({ title, message, onRetry }: ErrorFallbackProps) {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="text-center max-w-md">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-amber-100">
          <span className="text-xl">⚠</span>
        </div>
        <h3 className="text-sm font-semibold text-slate-700">
          {title || "This section is temporarily unavailable"}
        </h3>
        <p className="mt-2 text-xs text-slate-500 leading-relaxed">
          {message || "The data could not be loaded. This may be a temporary issue — please try again."}
        </p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-4 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-indigo-500"
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
}
