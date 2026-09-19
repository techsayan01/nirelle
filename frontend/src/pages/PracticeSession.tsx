import { ArrowLeft, ArrowRight, Lightbulb, UsersThree } from "@phosphor-icons/react"
import { useCallback, useEffect, useState } from "react"
import { Navigate, useNavigate, useParams } from "react-router-dom"
import { api } from "../api/client"
import type { DemoQuestion, MasteryState, SubSkill } from "../api/types"
import { AppShell } from "../components/AppShell"
import { Button } from "../components/Button"
import { Card } from "../components/Card"
import { Celebration } from "../components/Celebration"
import { ErrorBanner, Spinner } from "../components/Feedback"
import { Mascot } from "../components/Mascot"
import { MasteryMeter } from "../components/MasteryMeter"
import { QuestionFlowCard, type QuestionResponse } from "../components/QuestionFlow"
import { AT_HOME_ACTIONS, describeMisconception } from "../constants/misconceptions"
import { useSession } from "../state/SessionProvider"
import { bandForGrade } from "../theme/bands"
import { useAppBand } from "../theme/useAppBand"

type Phase =
  | "loading"
  | "diagnostic"
  | "remediation"
  | "retest"
  | "teacher-retest"
  | "resolved"
  | "escalated"
  | "error"

function pickQuestions(all: DemoQuestion[], count: number): DemoQuestion[] {
  return all.slice(0, Math.min(count, all.length))
}

export default function PracticeSession() {
  const { subSkillId } = useParams<{ subSkillId: string }>()
  const session = useSession()
  const navigate = useNavigate()
  const band = bandForGrade(session.grade)
  useAppBand(band)

  const [phase, setPhase] = useState<Phase>("loading")
  const [error, setError] = useState<string | null>(null)
  const [subSkill, setSubSkill] = useState<SubSkill | null>(null)
  const [allQuestions, setAllQuestions] = useState<DemoQuestion[]>([])
  const [activeQuestions, setActiveQuestions] = useState<DemoQuestion[]>([])
  const [state, setState] = useState<MasteryState | null>(null)
  const [personalizedContent, setPersonalizedContent] = useState<string>("")
  const [misconceptionTag, setMisconceptionTag] = useState<string | null>(null)
  const [strategiesTried, setStrategiesTried] = useState<string[]>([])

  const schoolId = session.schoolId
  const studentId = session.studentId!

  const bootstrap = useCallback(async () => {
    if (!subSkillId) return
    setPhase("loading")
    setError(null)
    try {
      const [skill, questions, current] = await Promise.all([
        api.getSubSkill(subSkillId),
        api.demoQuestions(subSkillId),
        api.getState(schoolId, studentId, subSkillId),
      ])
      setSubSkill(skill)
      setAllQuestions(questions)
      setState(current)

      if (current.stage === "resolved") {
        setPhase("resolved")
      } else if (current.stage === "escalated") {
        setPhase("escalated")
      } else if (current.stage === "teacher_retest") {
        setActiveQuestions(pickQuestions(questions, 1))
        setPhase("teacher-retest")
      } else {
        setActiveQuestions(pickQuestions(questions, current.recommended_question_count))
        setPhase("diagnostic")
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load this topic.")
      setPhase("error")
    }
  }, [subSkillId, schoolId, studentId])

  useEffect(() => {
    bootstrap()
  }, [bootstrap])

  async function recordGradedResponses(
    responses: QuestionResponse[],
    graded: { question_id: string; correct: boolean }[],
    stage: "diagnostic" | "retest" | "teacher_retest",
    tag: string | null,
  ) {
    const gradedById = new Map(graded.map((g) => [g.question_id, g.correct]))
    let latest: MasteryState | null = null
    for (const r of responses) {
      const correct = gradedById.get(r.question_id) ?? false
      latest = await api.recordAttempt(schoolId, studentId, subSkillId!, {
        correct,
        response_time_ms: r.response_time_ms,
        stage,
        misconception_tag: correct ? null : tag,
      })
    }
    if (latest) setState(latest)
    return latest
  }

  async function startRemediation(tag: string | null) {
    setMisconceptionTag(tag)
    await api.beginRemediation(schoolId, studentId, subSkillId!)

    const strategies = tag
      ? await api.listStrategies(subSkillId!, tag)
      : await api.listStrategies(subSkillId!)
    const strategy = strategies[0]

    if (strategy) {
      const { content } = await api.personalize(subSkillId!, {
        strategy_id: strategy.id,
        student_display_name: session.displayName,
        grade: session.grade,
      })
      setPersonalizedContent(content)
      // The demo curriculum has only one strategy per misconception, so a
      // student who trips the same misconception across several cycles
      // would otherwise get the identical strategy text repeated
      // verbatim in the teacher report - dedupe by content instead.
      setStrategiesTried((prev) => (prev.includes(strategy.content) ? prev : [...prev, strategy.content]))
    } else {
      setPersonalizedContent(
        "Let's slow down and walk through this kind of problem step by step next time.",
      )
    }
    setPhase("remediation")
  }

  async function escalateToTeacher(lastState: MasteryState) {
    const description = describeMisconception(misconceptionTag)
    await api.createEscalation(schoolId, {
      student_id: studentId,
      sub_skill_id: subSkillId!,
      misconception_description: `${session.displayName} ${description}.`,
      remediation_strategies_tried: strategiesTried.length > 0 ? strategiesTried : ["General walkthrough"],
      attempt_count: lastState.cycle_count,
      last_mastery_score: lastState.p_mastery,
      floor_mastery: 0.75,
    })
    await api.createParentReport(schoolId, {
      student_id: studentId,
      sub_skill_id: subSkillId!,
      sub_skill_name_plain: (subSkill?.name ?? "this topic").toLowerCase(),
      at_home_actions: AT_HOME_ACTIONS[subSkillId!] ?? ["Practice this skill together for a few minutes."],
    })
    setPhase("escalated")
  }

  async function handleDiagnosticComplete(responses: QuestionResponse[]) {
    try {
      const result = await api.demoSubmitResponses(subSkillId!, responses)
      const allCorrect = result.graded.every((g) => g.correct)

      await recordGradedResponses(responses, result.graded, "diagnostic", result.misconception_tag)

      if (allCorrect) {
        await api.beginRetest(schoolId, studentId, subSkillId!)
        const evaluated = await api.evaluateRetest(schoolId, studentId, subSkillId!)
        setState(evaluated)
        if (evaluated.stage === "escalated") await escalateToTeacher(evaluated)
        else if (evaluated.stage === "resolved") setPhase("resolved")
        else {
          setActiveQuestions(pickQuestions(allQuestions, evaluated.recommended_question_count))
          setPhase("diagnostic")
        }
      } else {
        await startRemediation(result.misconception_tag)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong grading that.")
      setPhase("error")
    }
  }

  async function handleRemediationContinue() {
    try {
      await api.beginRetest(schoolId, studentId, subSkillId!)
      setActiveQuestions(pickQuestions(allQuestions, state?.recommended_question_count ?? 2))
      setPhase("retest")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.")
      setPhase("error")
    }
  }

  async function handleRetestComplete(responses: QuestionResponse[]) {
    try {
      const result = await api.demoSubmitResponses(subSkillId!, responses)
      await recordGradedResponses(responses, result.graded, "retest", result.misconception_tag)
      const evaluated = await api.evaluateRetest(schoolId, studentId, subSkillId!)
      setState(evaluated)

      if (evaluated.stage === "resolved") setPhase("resolved")
      else if (evaluated.stage === "escalated") await escalateToTeacher(evaluated)
      else {
        // Per the BRD flowchart: still below floor with cycles left ->
        // back to a fresh diagnostic round, not straight to remediation.
        setMisconceptionTag(result.misconception_tag)
        setActiveQuestions(pickQuestions(allQuestions, evaluated.recommended_question_count))
        setPhase("diagnostic")
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong grading that.")
      setPhase("error")
    }
  }

  async function handleTeacherRetestComplete(responses: QuestionResponse[]) {
    try {
      const result = await api.demoSubmitResponses(subSkillId!, responses)
      await recordGradedResponses(responses, result.graded, "teacher_retest", result.misconception_tag)
      const finalState = await api.finalizeTeacherRetestStage(schoolId, studentId, subSkillId!)
      setState(finalState)
      setPhase("resolved")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong grading that.")
      setPhase("error")
    }
  }

  if (!session.studentId) return <Navigate to="/" replace />

  return (
    <AppShell eyebrow={subSkill?.chapter ?? "Practice"} title={subSkill?.name ?? "Loading..."} band={band}>
      <button
        onClick={() => navigate("/student")}
        className="mb-6 flex cursor-pointer items-center gap-1.5 text-sm font-semibold text-ink-muted hover:text-ink"
      >
        <ArrowLeft size={16} weight="bold" />
        My topics
      </button>

      {state && phase !== "loading" && phase !== "error" && (
        <div className="mb-6">
          <MasteryMeter value={state.p_mastery} band={band} />
        </div>
      )}

      {phase === "loading" && <Spinner label="Getting your practice ready" />}

      {phase === "error" && <ErrorBanner message={error ?? "Something went wrong."} onRetry={bootstrap} />}

      {phase === "diagnostic" && activeQuestions.length > 0 && (
        <QuestionFlowCard
          questions={activeQuestions}
          onComplete={handleDiagnosticComplete}
          continueLabel="Submit"
          band={band}
        />
      )}

      {phase === "remediation" && (
        <Card className="p-6 sm:p-8">
          <div className="flex items-start gap-4">
            {band === "elementary" ? (
              <Mascot mood="thinking" size={56} className="shrink-0" />
            ) : (
              <Lightbulb size={32} weight="fill" className="mt-1 shrink-0 text-secondary" />
            )}
            <div>
              <p className="font-display text-xl font-bold text-ink">Let's look at this differently</p>
              <p className="mt-2 whitespace-pre-line text-base leading-relaxed text-ink-muted">
                {personalizedContent}
              </p>
            </div>
          </div>
          <div className="mt-7 flex justify-end">
            <Button size="lg" onClick={handleRemediationContinue}>
              Try a similar problem
              <ArrowRight size={18} weight="bold" />
            </Button>
          </div>
        </Card>
      )}

      {phase === "retest" && activeQuestions.length > 0 && (
        <QuestionFlowCard
          questions={activeQuestions}
          onComplete={handleRetestComplete}
          continueLabel="Submit"
          band={band}
        />
      )}

      {phase === "teacher-retest" && activeQuestions.length > 0 && (
        <>
          <Card className="mb-5 flex items-start gap-4 p-6">
            <UsersThree size={32} weight="fill" className="mt-1 shrink-0 text-primary" />
            <div>
              <p className="font-display text-xl font-bold text-ink">Your teacher checked in with you</p>
              <p className="mt-2 text-base text-ink-muted">
                Let's do one quick problem to see how things are going now.
              </p>
            </div>
          </Card>
          <QuestionFlowCard
            questions={activeQuestions}
            onComplete={handleTeacherRetestComplete}
            continueLabel="Submit"
            band={band}
          />
        </>
      )}

      {phase === "resolved" && (
        <Card className="flex flex-col items-center py-12 text-center">
          <Celebration band={band} />
          <p className="font-display text-2xl font-bold text-ink">Nice work, {session.displayName.split(" ")[0]}!</p>
          <p className="mt-2 max-w-sm text-ink-muted">
            You've hit the mastery bar on {subSkill?.name ?? "this topic"}.
          </p>
          <Button className="mt-7" onClick={() => navigate("/student")}>
            Back to my topics
          </Button>
        </Card>
      )}

      {phase === "escalated" && (
        <Card className="flex flex-col items-center py-12 text-center">
          <UsersThree size={56} weight="fill" className="mb-4 text-primary" />
          <p className="font-display text-2xl font-bold text-ink">Let's get you some extra help</p>
          <p className="mt-2 max-w-sm text-ink-muted">
            You've given this a solid effort. We've let your teacher know exactly what to go over with you.
          </p>
          <Button className="mt-7" onClick={() => navigate("/student")}>
            Back to my topics
          </Button>
        </Card>
      )}
    </AppShell>
  )
}
