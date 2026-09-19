/** Auto-generated SVG visual for a fraction "n/d" - a bar cut into `d`
 * equal segments with `n` of them filled. Per the BRD: re-test problems
 * pair with an auto-generated visual (number line, fraction bar, etc.).
 *
 * Handles improper fractions (e.g. a "swap the numerator/denominator"
 * wrong-answer choice like 4/3) by drawing whole bars plus one partial
 * bar for the remainder - a single bar can't show more filled segments
 * than it has, so without this an improper fraction would render as an
 * undifferentiated solid block. */
interface FractionBarProps {
  label: string // e.g. "3/4"
  className?: string
}

const BAR_WIDTH = 240
const BAR_HEIGHT = 40
const MAX_WHOLE_BARS = 4

function SegmentedBar({ filled, of }: { filled: number; of: number }) {
  const segmentWidth = BAR_WIDTH / of
  return (
    <svg
      viewBox={`0 0 ${BAR_WIDTH} ${BAR_HEIGHT}`}
      width={BAR_WIDTH}
      height={BAR_HEIGHT}
      role="presentation"
    >
      <rect
        x={0.5}
        y={0.5}
        width={BAR_WIDTH - 1}
        height={BAR_HEIGHT - 1}
        rx={8}
        fill="var(--color-surface)"
        stroke="var(--color-line)"
      />
      {Array.from({ length: of }, (_, i) => (
        <rect
          key={i}
          x={i * segmentWidth}
          y={0}
          width={segmentWidth}
          height={BAR_HEIGHT}
          fill={i < filled ? "var(--color-primary)" : "transparent"}
          opacity={0.85}
        />
      ))}
      {Array.from({ length: of - 1 }, (_, i) => (
        <line
          key={i}
          x1={(i + 1) * segmentWidth}
          y1={0}
          x2={(i + 1) * segmentWidth}
          y2={BAR_HEIGHT}
          stroke="var(--color-line)"
          strokeWidth={1}
        />
      ))}
      <rect
        x={0.5}
        y={0.5}
        width={BAR_WIDTH - 1}
        height={BAR_HEIGHT - 1}
        rx={8}
        fill="none"
        stroke="var(--color-line)"
      />
    </svg>
  )
}

export function FractionBar({ label, className = "" }: FractionBarProps) {
  const [numRaw, denRaw] = label.split("/")
  const numerator = Number(numRaw)
  const denominator = Number(denRaw)

  if (!Number.isFinite(numerator) || !Number.isFinite(denominator) || denominator <= 0 || numerator < 0) {
    return null
  }

  const wholeCount = Math.min(Math.floor(numerator / denominator), MAX_WHOLE_BARS)
  const remainder = numerator - wholeCount * denominator

  return (
    <div
      className={`flex flex-col gap-1 ${className}`}
      role="img"
      aria-label={`Fraction bar showing ${numerator} of ${denominator} parts filled`}
    >
      {Array.from({ length: wholeCount }, (_, i) => (
        <SegmentedBar key={`whole-${i}`} filled={denominator} of={denominator} />
      ))}
      {(remainder > 0 || wholeCount === 0) && <SegmentedBar filled={remainder} of={denominator} />}
    </div>
  )
}
