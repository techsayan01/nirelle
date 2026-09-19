import { CheckCircle } from "@phosphor-icons/react"
import { useMemo } from "react"
import type { Band } from "../theme/bands"
import { CELEBRATION_INTENSITY } from "../theme/bands"
import { Mascot } from "./Mascot"

const CONFETTI_COLORS = [
  "var(--color-primary)",
  "var(--color-secondary)",
  "var(--color-accent)",
]

interface CelebrationProps {
  band: Band
}

export function Celebration({ band }: CelebrationProps) {
  const intensity = CELEBRATION_INTENSITY[band]

  const pieces = useMemo(
    () =>
      Array.from({ length: 18 }, (_, i) => ({
        left: `${(i * 37) % 100}%`,
        delay: `${(i % 6) * 70}ms`,
        rotate: `${(i % 2 === 0 ? 1 : -1) * (140 + (i % 5) * 30)}deg`,
        color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
      })),
    [],
  )

  if (intensity === "minimal") {
    return (
      <div className="flex flex-col items-center gap-3 py-4">
        <CheckCircle size={56} weight="fill" className="animate-pop-in text-success" />
      </div>
    )
  }

  return (
    <div className="relative flex flex-col items-center gap-4 py-4">
      {intensity === "full" && (
        <div className="pointer-events-none absolute inset-x-0 -top-4 h-32 overflow-hidden" aria-hidden="true">
          {pieces.map((p, i) => (
            <span
              key={i}
              className="absolute top-0 h-2.5 w-2.5 rounded-[2px]"
              style={{
                left: p.left,
                backgroundColor: p.color,
                animation: `confetti-fall 900ms ease-in ${p.delay} both`,
                // @ts-expect-error -- custom property for the keyframe above
                "--confetti-rotate": p.rotate,
              }}
            />
          ))}
        </div>
      )}
      {intensity === "full" ? (
        <Mascot mood="happy" size={88} className="animate-pop-in" />
      ) : (
        <CheckCircle size={64} weight="fill" className="animate-pop-in text-success" />
      )}
    </div>
  )
}
