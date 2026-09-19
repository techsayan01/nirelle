/** Human-readable descriptions of the demo curriculum's misconception
 * tags, for the teacher-escalation summary (nirelle.reports expects a
 * description of the misconception, not the corrective explanation text
 * shown to the student - see nirelle/seed_data.py for the tag list). */
export const MISCONCEPTION_DESCRIPTIONS: Record<string, string> = {
  num_denom_swap: "mixes up the numerator and denominator when writing a fraction",
  adds_denominators: "adds the denominators together instead of keeping them the same",
  skips_common_denominator: "adds fractions directly without finding a common denominator first",
  converts_only_one_fraction: "converts only one fraction to the common denominator before adding",
}

export function describeMisconception(tag: string | null): string {
  if (!tag) return "is making inconsistent errors that don't point to one clear misconception"
  return MISCONCEPTION_DESCRIPTIONS[tag] ?? "is showing a recurring error pattern on this skill"
}

/** 1-2 concrete at-home actions per sub-skill, matching the BRD's parent
 * report requirement. */
export const AT_HOME_ACTIONS: Record<string, string[]> = {
  "fractions.identify_parts": [
    "Cut a sandwich or fruit into equal pieces and ask them to name the fraction for how many pieces they take.",
  ],
  "fractions.add_like_denominators": [
    "Use a chocolate bar cut into equal squares - ask them to add up pieces from two helpings and say the fraction.",
  ],
  "fractions.add_unlike_denominators": [
    "Practice with measuring cups (e.g. 1/2 cup + 1/3 cup) to see why the amounts need to match before adding.",
  ],
}
