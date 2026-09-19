/** A single restrained, geometric mascot mark - used only in the
 * elementary band (empty states, celebration), never middle/high school.
 * Deliberately abstract (a rounded blob with a face) rather than
 * cartoon/clip-art, so it reads as a brand mark, not a stock asset. */
interface MascotProps {
  mood?: "happy" | "thinking"
  size?: number
  className?: string
}

export function Mascot({ mood = "happy", size = 96, className = "" }: MascotProps) {
  return (
    <svg
      viewBox="0 0 96 96"
      width={size}
      height={size}
      role="img"
      aria-label={mood === "happy" ? "Cheerful mascot" : "Thinking mascot"}
      className={className}
    >
      <path
        d="M48 8c22 0 36 14 36 34 0 22-14 38-36 38S12 64 12 42C12 22 26 8 48 8Z"
        fill="var(--color-primary)"
      />
      <circle cx={34} cy={44} r={5} fill="var(--color-on-primary)" />
      <circle cx={62} cy={44} r={5} fill="var(--color-on-primary)" />
      {mood === "happy" ? (
        <path
          d="M32 60c6 8 26 8 32 0"
          stroke="var(--color-on-primary)"
          strokeWidth={4}
          strokeLinecap="round"
          fill="none"
        />
      ) : (
        <path
          d="M34 62h28"
          stroke="var(--color-on-primary)"
          strokeWidth={4}
          strokeLinecap="round"
          fill="none"
        />
      )}
      <circle cx={20} cy={30} r={4} fill="var(--color-secondary)" />
      <circle cx={76} cy={26} r={3} fill="var(--color-accent)" />
    </svg>
  )
}
