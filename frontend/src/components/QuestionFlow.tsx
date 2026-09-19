import { ArrowRight } from "@phosphor-icons/react"
import { useEffect, useRef, useState } from "react"
import type { DemoQuestion } from "../api/types"
import { Button } from "./Button"
import { Card } from "./Card"
import { FractionBar } from "./FractionBar"

export interface QuestionResponse {
  question_id: string
  selected_choice_id: string
  response_time_ms: number
}

interface QuestionFlowProps {
  questions: DemoQuestion[]
  onComplete: (responses: QuestionResponse[]) => void
  continueLabel?: string
}

export function QuestionFlow({ questions, onComplete, continueLabel = "Continue" }: QuestionFlowProps) {
  const [index, setIndex] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [responses, setResponses] = useState<QuestionResponse[]>([])
  const startedAt = useRef<number>(performance.now())

  const question = questions[index]

  useEffect(() => {
    startedAt.current = performance.now()
    setSelectedId(null)
  }, [index]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!question) return null

  function handleContinue() {
    if (!selectedId) return
    const responseTimeMs = Math.round(performance.now() - startedAt.current)
    const next = [...responses, { question_id: question.id, selected_choice_id: selectedId, response_time_ms: responseTimeMs }]

    if (index + 1 < questions.length) {
      setResponses(next)
      setIndex(index + 1)
    } else {
      onComplete(next)
    }
  }

  return (
    <div>
      <div className="mb-5 flex items-center gap-1.5" aria-hidden="true">
        {questions.map((q, i) => (
          <span
            key={q.id}
            className={`h-1.5 flex-1 rounded-full transition-colors duration-300 ${
              i < index ? "bg-primary" : i === index ? "bg-primary/50" : "bg-black/[0.08]"
            }`}
          />
        ))}
      </div>
      <p className="mb-1 text-sm font-medium text-ink-muted">
        Question {index + 1} of {questions.length}
      </p>
      <h2 className="mb-6 font-display text-2xl font-bold text-ink sm:text-3xl">{question.prompt}</h2>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3" role="radiogroup" aria-label="Answer choices">
        {question.choices.map((choice) => {
          const active = selectedId === choice.id
          return (
            <button
              key={choice.id}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => setSelectedId(choice.id)}
              className={[
                "flex cursor-pointer flex-col items-center gap-3 rounded-[var(--radius-md)] border-2 p-4",
                "transition-all duration-150 ease-out active:scale-[0.97]",
                active
                  ? "border-primary bg-primary/[0.06] shadow-[var(--shadow-card)]"
                  : "border-line bg-surface hover:border-primary/50",
              ].join(" ")}
            >
              <FractionBar label={choice.label} className="pointer-events-none" />
              <span className="text-lg font-bold tabular-nums text-ink">{choice.label}</span>
            </button>
          )
        })}
      </div>

      <div className="mt-7 flex justify-end">
        <Button size="lg" onClick={handleContinue} disabled={!selectedId}>
          {continueLabel}
          <ArrowRight size={18} weight="bold" />
        </Button>
      </div>
    </div>
  )
}

export function QuestionFlowCard(props: QuestionFlowProps) {
  return (
    <Card className="p-6 sm:p-8">
      <QuestionFlow {...props} />
    </Card>
  )
}
