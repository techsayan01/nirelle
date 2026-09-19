import { useEffect } from "react"
import type { Band } from "./bands"

/** Sets the app-wide grade-band theme. Exactly one page is mounted at a
 * time (React Router), so whichever page calls this "owns" the theme for
 * as long as it's on screen - no coordination needed between pages. */
export function useAppBand(band: Band) {
  useEffect(() => {
    document.documentElement.dataset.band = band
  }, [band])
}
