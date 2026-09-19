import { ArrowRight, Books, SignOut } from "@phosphor-icons/react"
import { useEffect, useState } from "react"
import { Navigate, useNavigate } from "react-router-dom"
import { api } from "../api/client"
import { AppShell } from "../components/AppShell"
import { Button } from "../components/Button"
import { Card } from "../components/Card"
import { ErrorBanner, Spinner } from "../components/Feedback"
import { Mascot } from "../components/Mascot"
import { MasteryMeter } from "../components/MasteryMeter"
import type { MasteryState, SubSkill } from "../api/types"
import { useSession } from "../state/SessionProvider"
import { bandForGrade } from "../theme/bands"
import { useAppBand } from "../theme/useAppBand"

interface SubSkillWithState {
  subSkill: SubSkill
  state: MasteryState
}

export default function StudentHome() {
  const session = useSession()
  const navigate = useNavigate()
  const band = bandForGrade(session.grade)
  useAppBand(band)

  const [items, setItems] = useState<SubSkillWithState[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!session.studentId) return
    let cancelled = false
    setError(null)
    setItems(null)

    async function load() {
      try {
        const subSkills = await api.listSubSkills({ grade: session.grade, subject: "math" })
        const withState = await Promise.all(
          subSkills.map(async (subSkill) => ({
            subSkill,
            state: await api.getState(session.schoolId, session.studentId!, subSkill.id),
          })),
        )
        if (!cancelled) setItems(withState)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Couldn't load your topics.")
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [session.schoolId, session.studentId, session.grade])

  if (!session.role || !session.studentId) {
    return <Navigate to="/" replace />
  }

  return (
    <AppShell
      maxWidth="wide"
      band={band}
      eyebrow={`Grade ${session.grade}`}
      title={`Hi ${session.displayName.split(" ")[0]}!`}
      right={
        <Button variant="ghost" size="md" onClick={() => navigate("/")}>
          <SignOut size={18} />
          Switch
        </Button>
      }
    >
      {error && (
        <div className="mb-6">
          <ErrorBanner message={error} />
        </div>
      )}

      {!error && items === null && <Spinner label="Loading your topics" />}

      {items !== null && items.length === 0 && (
        <Card className="flex flex-col items-center py-14 text-center">
          {band === "elementary" && <Mascot mood="thinking" className="mb-4" />}
          {band !== "elementary" && <Books size={48} weight="light" className="mb-4 text-ink-muted" />}
          <p className="font-display text-xl font-bold text-ink">Nothing here yet for Grade {session.grade}</p>
          <p className="mt-2 max-w-sm text-sm text-ink-muted">
            This demo only has Grade 4 math (fractions) built out so far. Try switching to Grade 4 to see it in
            action.
          </p>
        </Card>
      )}

      {items !== null && items.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {items.map(({ subSkill, state }) => (
            <Card key={subSkill.id} className="flex flex-col">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{subSkill.chapter}</p>
              <p className="mt-1 font-display text-lg font-bold text-ink">{subSkill.name}</p>
              <div className="mt-4 mb-5">
                <MasteryMeter value={state.p_mastery} band={band} />
              </div>
              <Button
                className="mt-auto"
                onClick={() => navigate(`/student/practice/${subSkill.id}`)}
                variant={state.stage === "resolved" ? "secondary" : "primary"}
              >
                {state.stage === "resolved" ? "Practice again" : state.attempt_count > 0 ? "Continue" : "Start"}
                <ArrowRight size={18} weight="bold" />
              </Button>
            </Card>
          ))}
        </div>
      )}
    </AppShell>
  )
}
