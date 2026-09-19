import { ArrowLeft, CheckCircle, ChatCircleDots, ClipboardText, Target } from "@phosphor-icons/react"
import { useEffect, useState } from "react"
import { Navigate, useNavigate, useParams } from "react-router-dom"
import { api, ApiError } from "../api/client"
import type { TeacherEscalation } from "../api/types"
import { AppShell } from "../components/AppShell"
import { Button } from "../components/Button"
import { Card } from "../components/Card"
import { ErrorBanner, Spinner } from "../components/Feedback"
import { useSession } from "../state/SessionProvider"
import { useAppBand } from "../theme/useAppBand"

function Field({ icon: Icon, label, value }: { icon: typeof Target; label: string; value: string }) {
  return (
    <div className="flex gap-3">
      <Icon size={20} weight="bold" className="mt-0.5 shrink-0 text-primary" />
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{label}</p>
        <p className="mt-0.5 text-base leading-relaxed text-ink">{value}</p>
      </div>
    </div>
  )
}

export default function TeacherEscalationDetail() {
  const { escalationId } = useParams<{ escalationId: string }>()
  const session = useSession()
  const navigate = useNavigate()
  useAppBand("high")

  const [escalation, setEscalation] = useState<TeacherEscalation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [resolving, setResolving] = useState(false)

  useEffect(() => {
    if (!escalationId) return
    api
      .getEscalation(session.schoolId, Number(escalationId))
      .then(setEscalation)
      .catch((err) => setError(err instanceof Error ? err.message : "Couldn't load this case."))
  }, [session.schoolId, escalationId])

  async function handleResolve() {
    if (!escalation) return
    setResolving(true)
    setError(null)
    try {
      const resolved = await api.resolveEscalation(
        session.schoolId,
        escalation.id,
        session.displayName || "Teacher",
      )
      setEscalation(resolved)
      // Advance the student's mastery-state loop: ESCALATED -> TEACHER_RETEST.
      // If it's already past that stage (e.g. re-clicked), ignore the conflict.
      try {
        await api.resolveTeacherEscalationStage(session.schoolId, escalation.student_id, escalation.sub_skill_id)
      } catch (err) {
        if (!(err instanceof ApiError && err.status === 409)) throw err
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't mark this resolved.")
    } finally {
      setResolving(false)
    }
  }

  if (!session.role) return <Navigate to="/" replace />

  return (
    <AppShell eyebrow="Teacher" title="Case detail">
      <button
        onClick={() => navigate("/teacher")}
        className="mb-6 flex cursor-pointer items-center gap-1.5 text-sm font-semibold text-ink-muted hover:text-ink"
      >
        <ArrowLeft size={16} weight="bold" />
        All cases
      </button>

      {error && (
        <div className="mb-5">
          <ErrorBanner message={error} />
        </div>
      )}

      {!escalation && !error && <Spinner label="Loading case" />}

      {escalation && (
        <Card className="flex flex-col gap-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Student</p>
            <p className="font-display text-2xl font-bold text-ink">
              {escalation.student_id} <span className="text-ink-muted">· {escalation.class_section}</span>
            </p>
          </div>

          <Field icon={ClipboardText} label="What's going on" value={escalation.misconception_summary} />
          <Field
            icon={ChatCircleDots}
            label={`Already tried (${escalation.attempt_count} attempt${escalation.attempt_count === 1 ? "" : "s"})`}
            value={escalation.remediation_attempted}
          />
          <Field icon={Target} label="Focus for your 1-on-1" value={escalation.one_on_one_focus} />

          <div className="border-t border-line pt-5">
            {escalation.resolved_at ? (
              <p className="flex items-center gap-2 text-sm font-semibold text-success">
                <CheckCircle size={20} weight="fill" />
                Resolved by {escalation.resolved_by}
              </p>
            ) : (
              <>
                <p className="mb-3 text-sm text-ink-muted">
                  Once you've had the 1-on-1, mark this resolved - the student gets one more quick check-in and
                  their mastery score updates from that, not from your say-so.
                </p>
                <Button onClick={handleResolve} loading={resolving}>
                  I've had the 1-on-1 - mark resolved
                </Button>
              </>
            )}
          </div>
        </Card>
      )}
    </AppShell>
  )
}
