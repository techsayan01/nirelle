import { type ButtonHTMLAttributes, forwardRef } from "react"

type Variant = "primary" | "secondary" | "ghost" | "danger"
type Size = "md" | "lg"

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
}

const VARIANT_CLASSES: Record<Variant, string> = {
  primary:
    "bg-primary text-on-primary hover:bg-primary-hover active:scale-[0.97] shadow-[var(--shadow-card)]",
  secondary:
    "bg-surface text-ink border border-line hover:border-primary hover:text-primary active:scale-[0.97]",
  ghost: "bg-transparent text-ink-muted hover:bg-black/[0.04] hover:text-ink active:scale-[0.97]",
  danger: "bg-danger text-white hover:opacity-90 active:scale-[0.97]",
}

const SIZE_CLASSES: Record<Size, string> = {
  md: "h-11 px-5 text-[15px] gap-2",
  lg: "h-12 px-7 text-base gap-2.5",
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading = false, disabled, className = "", children, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={[
        "inline-flex cursor-pointer items-center justify-center rounded-[var(--radius-md)] font-semibold",
        "transition-all duration-200 ease-out disabled:cursor-not-allowed disabled:opacity-40 disabled:active:scale-100",
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        className,
      ].join(" ")}
      {...rest}
    >
      {loading && (
        <span
          className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
          aria-hidden="true"
        />
      )}
      {children}
    </button>
  )
})
