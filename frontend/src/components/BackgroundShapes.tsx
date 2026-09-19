/** Ambient background decoration for the elementary band only - a few
 * slow-drifting blurred blobs, low opacity, purely behind content. One
 * "creative" flourish that costs nothing structurally (absolute
 * positioned, non-interactive) rather than a decorated-everywhere
 * approach - the everyday UI chrome stays clean per-band via tokens, this
 * just adds a sense of a livelier world for the younger band. */
export function BackgroundShapes() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div
        className="animate-blob-drift absolute -left-16 top-24 h-56 w-56 rounded-full opacity-[0.14] blur-3xl"
        style={{ background: "var(--color-secondary)" }}
      />
      <div
        className="animate-blob-drift absolute -right-20 top-72 h-72 w-72 rounded-full opacity-[0.12] blur-3xl"
        style={{ background: "var(--color-accent)", animationDelay: "-5s" }}
      />
      <div
        className="animate-blob-drift absolute left-1/3 top-[520px] h-44 w-44 rounded-full opacity-[0.1] blur-3xl"
        style={{ background: "var(--color-primary)", animationDelay: "-9s" }}
      />
    </div>
  )
}
