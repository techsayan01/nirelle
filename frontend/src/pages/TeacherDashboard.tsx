import { ArrowRight, CheckCircle, SignOut, UsersThree } from "@phosphor-icons/react"
import { useEffect, useState } from "react"
import { Navigate, useNavigate } from "react-router-dom"
import { api } from "../api/client"
import type { TeacherEscalation } from "../api/types"
import { AppShell } from "../components/AppShell"
import { Button } from "../components/Button"
import { Card } from "../components/Card"
import { ErrorBanner, Spinner } from "../components/Feedback"
import { useSession } from "../state/SessionProvider"
import { useAppBand } from "../theme/useAppBand"

export default function TeacherDashboard() {
  useAppBand("high")
  const session = useSession()
  const navigate = useNavigate()

  const [tab, setTab] = useState<"open" | "resolved">("open")
  const [escalations, setEscalations] = useState<TeacherEscalation[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setEscalations(null)
    setError(null)
    api
      .listEscalations(session.schoolId, tab === "open" ? false : true)
      .then((rows) => !cancelled && setEscalations(rows))
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : "Couldn't load cases."))
    return () => {
      cancelled = true
    }
  }, [session.schoolId, tab])

  if (!session.role) return <Navigate to="/" replace />

  return (
    <AppShell
      maxWidth="wide"
      eyebrow="Teacher"
      title="Flagged students"
      right={
        <Button variant="ghost" size="md" onClick={() => navigate("/")}>
          <SignOut size={18} />
          Switch
        </Button>
      }
    >
      <div className="mb-6 flex gap-2">
        {(["open", "resolved"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={[
              "cursor-pointer rounded-[var(--radius-pill)] px-4 py-2 text-sm font-semibold transition-colors",
              tab === t ? "bg-primary text-on-primary" : "bg-black/[0.05] text-ink-muted hover:bg-black/[0.08]",
            ].join(" ")}
          >
            {t === "open" ? "Needs attention" : "Resolved"}
          </button>
        ))}
      </div>

      {error && <ErrorBanner message={error} />}
      {!error && escalations === null && <Spinner label="Loading cases" />}

      {escalations !== null && escalations.length === 0 && (
        <Card className="flex flex-col items-center py-14 text-center">
          <CheckCircle size={48} weight="light" className="mb-4 text-ink-muted" />
          <p className="font-display text-lg font-bold text-ink">
            {tab === "open" ? "Nothing needs your attention right now" : "No resolved cases yet"}
          </p>
        </Card>
      )}

      {escalations !== null && escalations.length > 0 && (
        <div className="flex flex-col gap-3">
          {escalations.map((e) => (
            <Card
              key={e.id}
              interactive
              onClick={() => navigate(`/teacher/escalations/${e.id}`)}
              className="flex items-center justify-between gap-4"
            >
              <div className="flex items-center gap-4">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                  <UsersThree size={22} weight="fill" />
                </span>
                <div>
                  <p className="font-semibold text-ink">
                    {e.student_id} <span className="text-ink-muted">· {e.class_section}</span>
                  </p>
                  <p className="mt-0.5 line-clamp-1 text-sm text-ink-muted">{e.misconception_summary}</p>
                </div>
              </div>
              <ArrowRight size={18} className="shrink-0 text-ink-muted" />
            </Card>
          ))}
        </div>
      )}
    </AppShell>
  )
}
