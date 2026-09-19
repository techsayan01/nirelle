import { WarningCircle } from "@phosphor-icons/react"
import { Button } from "./Button"

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-ink-muted" role="status">
      <span className="h-6 w-6 animate-spin rounded-full border-2 border-current border-t-transparent" />
      <span className="text-sm font-medium">{label}...</span>
    </div>
  )
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-start gap-3 rounded-[var(--radius-md)] border border-danger/20 bg-danger-bg p-4">
      <WarningCircle size={22} weight="fill" className="mt-0.5 shrink-0 text-danger" aria-hidden="true" />
      <div className="flex-1">
        <p className="text-sm font-medium text-danger">{message}</p>
        {onRetry && (
          <Button variant="secondary" size="md" className="mt-3" onClick={onRetry}>
            Try again
          </Button>
        )}
      </div>
    </div>
  )
}
