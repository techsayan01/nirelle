import { ArrowSquareOut, ChalkboardTeacher, ChartLineUp, GraduationCap, House } from "@phosphor-icons/react"
import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { api } from "../api/client"
import { AppShell } from "../components/AppShell"
import { Button } from "../components/Button"
import { Card } from "../components/Card"
import { ErrorBanner } from "../components/Feedback"
import { slugifyStudentId, useSession, type Role } from "../state/SessionProvider"
import { bandForGrade, BAND_LABEL } from "../theme/bands"
import { useAppBand } from "../theme/useAppBand"

const GRADE_GROUPS: { label: string; grades: number[] }[] = [
  { label: "Elementary", grades: [1, 2, 3, 4, 5] },
  { label: "Middle School", grades: [6, 7, 8] },
  { label: "High School", grades: [9, 10, 11, 12] },
]

const ROLE_OPTIONS: { role: Role; label: string; description: string; icon: typeof House }[] = [
  { role: "student", label: "I'm a student", description: "Practice and get help on a skill", icon: GraduationCap },
  { role: "teacher", label: "I'm a teacher", description: "Review flagged students", icon: ChalkboardTeacher },
  { role: "parent", label: "I'm a parent", description: "See how your child is doing", icon: House },
]

export default function Landing() {
  const navigate = useNavigate()
  const session = useSession()
  const [role, setRole] = useState<Role | null>(session.role)
  const [grade, setGrade] = useState(session.grade)
  const [name, setName] = useState(session.displayName)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const previewBand = role === "student" ? bandForGrade(grade) : "high"
  useAppBand(previewBand)

  async function handleStart() {
    if (!role || !name.trim()) return
    setBusy(true)
    setError(null)
    try {
      await api.ensureSchool(session.schoolId, "Green Valley School (Demo)")

      session.setRole(role)
      session.setDisplayName(name.trim())

      if (role === "student") {
        session.setGrade(grade)
        const studentId = session.studentId ?? slugifyStudentId(name)
        await api.ensureStudent(session.schoolId, {
          id: studentId,
          class_section: `${grade}A`,
          display_name: name.trim(),
        })
        session.setStudentId(studentId)
        navigate("/student")
      } else if (role === "teacher") {
        navigate("/teacher")
      } else {
        navigate("/parent")
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <AppShell maxWidth="wide">
      <div className="mx-auto max-w-3xl">
        <p className="mb-2 text-sm font-semibold uppercase tracking-wide text-primary">Nirelle</p>
        <h1 className="mb-3 font-display text-4xl font-bold text-ink sm:text-5xl">
          Catch it before the test.
        </h1>
        <p className="mb-10 max-w-xl text-lg text-ink-muted">
          A quick check, a clear explanation, and one more try - before a small gap becomes a bad grade.
        </p>

        <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {ROLE_OPTIONS.map(({ role: r, label, description, icon: Icon }) => {
            const active = role === r
            return (
              <Card
                key={r}
                interactive
                onClick={() => setRole(r)}
                className={active ? "border-primary ring-2 ring-primary/30" : ""}
              >
                <Icon size={28} weight={active ? "fill" : "regular"} className="mb-3 text-primary" />
                <p className="font-display text-lg font-bold text-ink">{label}</p>
                <p className="mt-1 text-sm text-ink-muted">{description}</p>
              </Card>
            )
          })}
        </div>

        {role === "student" && (
          <Card className="mb-6">
            <p className="mb-3 text-sm font-semibold text-ink">What grade are you in?</p>
            <div className="flex flex-col gap-4">
              {GRADE_GROUPS.map((group) => (
                <div key={group.label}>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                    {group.label}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {group.grades.map((g) => (
                      <button
                        key={g}
                        type="button"
                        onClick={() => setGrade(g)}
                        aria-pressed={grade === g}
                        className={[
                          "flex h-11 w-11 cursor-pointer items-center justify-center rounded-[var(--radius-sm)] border-2 font-bold transition-all duration-150",
                          grade === g
                            ? "border-primary bg-primary text-on-primary"
                            : "border-line bg-surface text-ink hover:border-primary/50",
                        ].join(" ")}
                      >
                        {g}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-4 text-sm text-ink-muted">
              Grade {grade} · <span className="font-medium text-ink">{BAND_LABEL[previewBand]}</span> experience
            </p>
          </Card>
        )}

        {role && (
          <Card className="mb-6">
            <label htmlFor="display-name" className="mb-2 block text-sm font-semibold text-ink">
              {role === "student" ? "What's your name?" : "Your name"}
            </label>
            <input
              id="display-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Asha"
              className="h-11 w-full rounded-[var(--radius-sm)] border border-line bg-surface px-4 text-base text-ink outline-none transition-colors focus:border-primary"
              autoComplete="name"
            />
          </Card>
        )}

        {error && (
          <div className="mb-6">
            <ErrorBanner message={error} onRetry={handleStart} />
          </div>
        )}

        <Button size="lg" onClick={handleStart} disabled={!role || !name.trim()} loading={busy}>
          Let's go
        </Button>

        <a
          href="https://claude.ai/artifact/6tbgUwBYq8eHFmmiQkvdQD"
          target="_blank"
          rel="noopener noreferrer"
          className="mt-8 flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors hover:text-primary"
        >
          <ChartLineUp size={16} weight="bold" />
          See why recency-weighted BKT beats the alternatives
          <ArrowSquareOut size={14} />
        </a>
      </div>
    </AppShell>
  )
}
