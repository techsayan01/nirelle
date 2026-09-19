import { Heart, House, SignOut } from "@phosphor-icons/react"
import { useEffect, useState } from "react"
import { Navigate, useNavigate } from "react-router-dom"
import { api } from "../api/client"
import type { ParentReport } from "../api/types"
import { AppShell } from "../components/AppShell"
import { Button } from "../components/Button"
import { Card } from "../components/Card"
import { ErrorBanner, Spinner } from "../components/Feedback"
import { useSession } from "../state/SessionProvider"
import { useAppBand } from "../theme/useAppBand"

export default function ParentView() {
  useAppBand("high")
  const session = useSession()
  const navigate = useNavigate()

  const [studentId, setStudentId] = useState(session.studentId ?? "")
  const [lookedUp, setLookedUp] = useState(!!session.studentId)
  const [reports, setReports] = useState<ParentReport[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!lookedUp || !studentId) return
    let cancelled = false
    setReports(null)
    setError(null)
    api
      .listParentReports(session.schoolId, studentId)
      .then((rows) => !cancelled && setReports(rows))
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : "Couldn't load reports."))
    return () => {
      cancelled = true
    }
  }, [session.schoolId, studentId, lookedUp])

  if (!session.role) return <Navigate to="/" replace />

  return (
    <AppShell
      eyebrow="Parent"
      title="How your child is doing"
      right={
        <Button variant="ghost" size="md" onClick={() => navigate("/")}>
          <SignOut size={18} />
          Switch
        </Button>
      }
    >
      {!lookedUp && (
        <Card className="mb-6">
          <label htmlFor="student-id" className="mb-2 block text-sm font-semibold text-ink">
            Your child's student ID
          </label>
          <p className="mb-3 text-sm text-ink-muted">
            This is the ID your child used when they set up practice on this device or shared with you.
          </p>
          <div className="flex gap-3">
            <input
              id="student-id"
              value={studentId}
              onChange={(e) => setStudentId(e.target.value)}
              placeholder="e.g. asha-4f2c"
              className="h-11 flex-1 rounded-[var(--radius-sm)] border border-line bg-surface px-4 text-base text-ink outline-none focus:border-primary"
            />
            <Button onClick={() => setLookedUp(true)} disabled={!studentId.trim()}>
              View
            </Button>
          </div>
        </Card>
      )}

      {lookedUp && (
        <>
          {error && (
            <div className="mb-5">
              <ErrorBanner message={error} />
            </div>
          )}

          {!error && reports === null && <Spinner label="Loading" />}

          {reports !== null && reports.length === 0 && (
            <Card className="flex flex-col items-center py-14 text-center">
              <House size={48} weight="light" className="mb-4 text-ink-muted" />
              <p className="font-display text-lg font-bold text-ink">All quiet for now</p>
              <p className="mt-2 max-w-sm text-sm text-ink-muted">
                No updates yet for student ID <span className="font-mono">{studentId}</span>. We'll share a note
                here if your child needs extra support at home.
              </p>
              <Button variant="secondary" className="mt-5" onClick={() => setLookedUp(false)}>
                Look up a different student
              </Button>
            </Card>
          )}

          {reports !== null && reports.length > 0 && (
            <div className="flex flex-col gap-4">
              {reports.map((r) => (
                <Card key={r.id} className="flex items-start gap-4">
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-accent/10 text-accent">
                    <Heart size={20} weight="fill" />
                  </span>
                  <div>
                    <p className="text-base leading-relaxed text-ink">{r.plain_summary}</p>
                    <div className="mt-3 rounded-[var(--radius-sm)] bg-black/[0.03] p-3">
                      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                        Try this at home
                      </p>
                      {r.at_home_actions.split("\n").map((action, i) => (
                        <p key={i} className="text-sm text-ink">
                          {action}
                        </p>
                      ))}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </AppShell>
  )
}
