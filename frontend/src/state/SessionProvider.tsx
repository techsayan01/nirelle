import { createContext, useContext, useEffect, useState, type ReactNode } from "react"

export type Role = "student" | "teacher" | "parent"

export interface SessionState {
  schoolId: string
  role: Role | null
  grade: number
  displayName: string
  studentId: string | null
}

interface SessionContextValue extends SessionState {
  setRole: (role: Role) => void
  setGrade: (grade: number) => void
  setDisplayName: (name: string) => void
  setStudentId: (id: string | null) => void
  reset: () => void
}

const STORAGE_KEY = "nirelle.session.v1"
const DEFAULT_SCHOOL_ID = "demo-school"

const DEFAULTS: SessionState = {
  schoolId: DEFAULT_SCHOOL_ID,
  role: null,
  grade: 4,
  displayName: "",
  studentId: null,
}

function loadInitial(): SessionState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return { ...DEFAULTS, ...JSON.parse(raw) }
  } catch {
    // private browsing / blocked storage - start fresh
  }
  return DEFAULTS
}

const SessionContext = createContext<SessionContextValue | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>(loadInitial)

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    } catch {
      // ignore - session just won't survive a reload
    }
  }, [state])

  const value: SessionContextValue = {
    ...state,
    setRole: (role) => setState((s) => ({ ...s, role })),
    setGrade: (grade) => setState((s) => ({ ...s, grade })),
    setDisplayName: (displayName) => setState((s) => ({ ...s, displayName })),
    setStudentId: (studentId) => setState((s) => ({ ...s, studentId })),
    reset: () => setState(DEFAULTS),
  }

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error("useSession must be used within SessionProvider")
  return ctx
}

/** A short, URL/ID-safe slug from a display name, plus a random suffix so
 * two students with the same first name don't collide within a school. */
export function slugifyStudentId(displayName: string): string {
  const base =
    displayName
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "") || "student"
  const suffix = Math.random().toString(36).slice(2, 6)
  return `${base}-${suffix}`
}
