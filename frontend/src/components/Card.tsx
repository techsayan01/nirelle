import type { HTMLAttributes, ReactNode } from "react"

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  interactive?: boolean
  children: ReactNode
}

export function Card({ interactive = false, className = "", children, ...rest }: CardProps) {
  return (
    <div
      className={[
        "rounded-[var(--radius-lg)] border border-line bg-surface p-6",
        "shadow-[var(--shadow-card)]",
        interactive &&
          "cursor-pointer transition-all duration-200 ease-out hover:-translate-y-0.5 hover:shadow-[var(--shadow-card-hover)]",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      {...rest}
    >
      {children}
    </div>
  )
}
