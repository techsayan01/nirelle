import { Star } from "@phosphor-icons/react"
import type { Band } from "../theme/bands"

interface MasteryMeterProps {
  value: number // 0-1
  floor?: number // 0-1
  label?: string
  band?: Band
}

export function MasteryMeter({ value, floor = 0.75, label = "Mastery", band }: MasteryMeterProps) {
  const pct = Math.round(value * 100)
  const playful = band === "elementary"
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className="text-sm font-medium text-ink-muted">{label}</span>
        <span className="text-sm font-bold tabular-nums text-ink">{pct}%</span>
      </div>
      <div className={playful ? "relative pt-2" : "relative"}>
        <div
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={label}
          className="relative h-3 overflow-hidden rounded-[var(--radius-pill)] bg-black/[0.06]"
        >
          <div
            className="h-full rounded-[var(--radius-pill)] bg-primary transition-[width] duration-500 ease-out"
            style={{ width: `${pct}%` }}
          />
          <div
            className="absolute top-0 h-full w-0.5 bg-ink/25"
            style={{ left: `${Math.round(floor * 100)}%` }}
            title={`Floor: ${Math.round(floor * 100)}%`}
          />
        </div>
        {playful && (
          <Star
            weight="fill"
            size={18}
            className="absolute top-0 -translate-x-1/2 text-secondary transition-[left] duration-500 ease-out"
            style={{ left: `${pct}%` }}
            aria-hidden="true"
          />
        )}
      </div>
    </div>
  )
}
