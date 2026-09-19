export type Band = "elementary" | "middle" | "high"

export function bandForGrade(grade: number): Band {
  if (grade <= 5) return "elementary"
  if (grade <= 8) return "middle"
  return "high"
}

export const BAND_LABEL: Record<Band, string> = {
  elementary: "Elementary",
  middle: "Middle School",
  high: "High School",
}

/** Phosphor icon weight per band - one icon family throughout, refinement
 * expressed through weight instead of swapping icon sets. */
export const ICON_WEIGHT: Record<Band, "duotone" | "regular" | "light"> = {
  elementary: "duotone",
  middle: "regular",
  high: "light",
}

/** How much celebratory motion a band gets on success (confetti burst vs.
 * a calm checkmark) - see Celebration.tsx. */
export const CELEBRATION_INTENSITY: Record<Band, "full" | "moderate" | "minimal"> = {
  elementary: "full",
  middle: "moderate",
  high: "minimal",
}
