export type LoopStage =
  | "diagnostic"
  | "remediation"
  | "retest"
  | "resolved"
  | "escalated"
  | "teacher_retest"

export interface School {
  id: string
  name: string
}

export interface SubSkill {
  id: string
  name: string
  grade: number
  subject: string
  chapter: string
  p_init: number
  p_learn: number
  p_slip: number
  p_guess: number
}

export interface ExplanationStrategy {
  id: number
  sub_skill_id: string
  misconception_tag: string
  content: string
  rank: number
}

export interface Student {
  id: string
  school_id: string
  class_section: string
  display_name: string
}

export interface MasteryState {
  student_id: string
  sub_skill_id: string
  p_mastery: number
  stage: LoopStage
  cycle_count: number
  attempt_count: number
  recommended_question_count: number
}

export interface DemoChoice {
  id: string
  label: string
}

export interface DemoQuestion {
  id: string
  sub_skill_id: string
  difficulty: number
  prompt: string
  choices: DemoChoice[]
}

export interface DemoGradedResponse {
  question_id: string
  correct: boolean
}

export type MisconceptionConfidence = "none" | "ambiguous" | "confident"

export interface DemoSubmissionResult {
  graded: DemoGradedResponse[]
  misconception_tag: string | null
  misconception_confidence: MisconceptionConfidence
}

export interface TeacherEscalation {
  id: number
  school_id: string
  class_section: string
  student_id: string
  sub_skill_id: string
  misconception_summary: string
  remediation_attempted: string
  attempt_count: number
  one_on_one_focus: string
  resolved_at: string | null
  resolved_by: string | null
}

export interface ParentReport {
  id: number
  school_id: string
  class_section: string
  student_id: string
  sub_skill_id: string
  plain_summary: string
  at_home_actions: string
}
