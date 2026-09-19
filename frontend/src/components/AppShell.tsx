import { GraduationCap } from "@phosphor-icons/react"
import type { ReactNode } from "react"
import { Link } from "react-router-dom"

interface AppShellProps {
  eyebrow?: string
  title?: string
  right?: ReactNode
  children: ReactNode
  maxWidth?: "narrow" | "wide"
}

export function AppShell({ eyebrow, title, right, children, maxWidth = "narrow" }: AppShellProps) {
  return (
    <div className="min-h-dvh bg-app-bg">
      <header className="border-b border-line bg-surface/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link to="/" className="flex items-center gap-2 font-display text-lg font-bold text-ink no-underline">
            <span className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-sm)] bg-primary text-on-primary">
              <GraduationCap size={18} weight="fill" />
            </span>
            Nirelle
          </Link>
          {right}
        </div>
      </header>

      <main className={`mx-auto px-4 py-10 sm:px-6 ${maxWidth === "wide" ? "max-w-6xl" : "max-w-2xl"}`}>
        {(eyebrow || title) && (
          <div className="mb-8">
            {eyebrow && (
              <p className="mb-1.5 text-sm font-semibold uppercase tracking-wide text-primary">{eyebrow}</p>
            )}
            {title && (
              <h1 className="font-display text-3xl font-bold text-ink sm:text-4xl">{title}</h1>
            )}
          </div>
        )}
        {children}
      </main>
    </div>
  )
}
