import { AlertTriangle, SearchX } from "lucide-react";

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <SearchX className="w-8 h-8 text-fg-subtle mb-3" />
      <p className="text-sm font-medium text-fg-muted">{title}</p>
      {hint && <p className="text-xs text-fg-subtle mt-1 max-w-xs">{hint}</p>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <AlertTriangle className="w-8 h-8 text-orange-500 mb-3" />
      <p className="text-sm font-medium text-fg">Unable to load data</p>
      <p className="text-xs text-fg-subtle mt-1 max-w-xs">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 px-4 py-1.5 rounded-lg bg-accent/15 text-accent border border-accent/20 text-xs font-medium hover:bg-accent/25 transition-colors"
        >
          Try again
        </button>
      )}
    </div>
  );
}