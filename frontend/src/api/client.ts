import type {
  DemoQuestion,
  DemoSubmissionResult,
  ExplanationStrategy,
  MasteryState,
  ParentReport,
  School,
  Student,
  SubSkill,
  TeacherEscalation,
} from "./types"

const BASE = "/api"

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = "ApiError"
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      // non-JSON error body; fall back to statusText
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

const get = <T>(path: string) => request<T>(path)
const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) })

function query(params: Record<string, string | number | boolean | undefined>): string {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) qs.set(key, String(value))
  }
  const s = qs.toString()
  return s ? `?${s}` : ""
}

/** POST that treats 409 (already exists) as success - the demo has no
 * login step, so "create or resume" is the natural flow for schools and
 * students created on a previous visit. */
async function postIdempotent<T>(path: string, body: unknown, onConflict: () => T | Promise<T>): Promise<T> {
  try {
    return await post<T>(path, body)
  } catch (err) {
    if (err instanceof ApiError && err.status === 409) return onConflict()
    throw err
  }
}

export const api = {
  // schools
  ensureSchool: (id: string, name: string) =>
    postIdempotent<School>("/schools", { id, name }, () => ({ id, name })),

  // students
  ensureStudent: (schoolId: string, student: { id: string; class_section: string; display_name: string }) =>
    postIdempotent<Student>(`/schools/${schoolId}/students`, student, () =>
      get<Student>(`/schools/${schoolId}/students/${student.id}`),
    ),
  getStudent: (schoolId: string, studentId: string) =>
    get<Student>(`/schools/${schoolId}/students/${studentId}`),

  // curriculum
  listSubSkills: (params: { grade?: number; subject?: string } = {}) =>
    get<SubSkill[]>(`/curriculum/sub-skills${query(params)}`),
  getSubSkill: (subSkillId: string) => get<SubSkill>(`/curriculum/sub-skills/${subSkillId}`),
  listStrategies: (subSkillId: string, misconceptionTag?: string) =>
    get<ExplanationStrategy[]>(
      `/curriculum/sub-skills/${subSkillId}/strategies${query({ misconception_tag: misconceptionTag })}`,
    ),
  personalize: (
    subSkillId: string,
    body: { strategy_id: number; student_display_name: string; grade: number; tone_hint?: string },
  ) => post<{ content: string }>(`/curriculum/sub-skills/${subSkillId}/personalize`, body),

  // demo diagnostics
  demoQuestions: (subSkillId: string) => get<DemoQuestion[]>(`/demo/sub-skills/${subSkillId}/questions`),
  demoSubmitResponses: (
    subSkillId: string,
    responses: { question_id: string; selected_choice_id: string; response_time_ms: number }[],
  ) => post<DemoSubmissionResult>(`/demo/sub-skills/${subSkillId}/responses`, { responses }),

  // mastery loop
  getState: (schoolId: string, studentId: string, subSkillId: string) =>
    get<MasteryState>(`/schools/${schoolId}/students/${studentId}/subskills/${subSkillId}`),
  recordAttempt: (
    schoolId: string,
    studentId: string,
    subSkillId: string,
    attempt: { correct: boolean; response_time_ms: number; stage: string; misconception_tag?: string | null },
  ) =>
    post<MasteryState>(
      `/schools/${schoolId}/students/${studentId}/subskills/${subSkillId}/attempts`,
      attempt,
    ),
  beginRemediation: (schoolId: string, studentId: string, subSkillId: string) =>
    post<MasteryState>(
      `/schools/${schoolId}/students/${studentId}/subskills/${subSkillId}/begin-remediation`,
    ),
  beginRetest: (schoolId: string, studentId: string, subSkillId: string) =>
    post<MasteryState>(`/schools/${schoolId}/students/${studentId}/subskills/${subSkillId}/begin-retest`),
  evaluateRetest: (schoolId: string, studentId: string, subSkillId: string) =>
    post<MasteryState>(
      `/schools/${schoolId}/students/${studentId}/subskills/${subSkillId}/evaluate-retest`,
    ),
  /** Teacher's "1-on-1 done" action: ESCALATED -> TEACHER_RETEST on the
   * mastery state (distinct from resolveEscalation, which closes the
   * escalation *report* row). */
  resolveTeacherEscalationStage: (schoolId: string, studentId: string, subSkillId: string) =>
    post<MasteryState>(
      `/schools/${schoolId}/students/${studentId}/subskills/${subSkillId}/resolve-teacher-escalation`,
    ),
  /** Student's one follow-up re-test after the teacher stepped in:
   * TEACHER_RETEST -> RESOLVED. */
  finalizeTeacherRetestStage: (schoolId: string, studentId: string, subSkillId: string) =>
    post<MasteryState>(
      `/schools/${schoolId}/students/${studentId}/subskills/${subSkillId}/finalize-teacher-retest`,
    ),

  // escalations / parent reports
  listEscalations: (schoolId: string, resolved?: boolean) =>
    get<TeacherEscalation[]>(`/schools/${schoolId}/escalations${query({ resolved })}`),
  getEscalation: (schoolId: string, escalationId: number) =>
    get<TeacherEscalation>(`/schools/${schoolId}/escalations/${escalationId}`),
  createEscalation: (
    schoolId: string,
    body: {
      student_id: string
      sub_skill_id: string
      misconception_description: string
      remediation_strategies_tried: string[]
      attempt_count: number
      last_mastery_score: number
      floor_mastery: number
    },
  ) => post<TeacherEscalation>(`/schools/${schoolId}/escalations`, body),
  resolveEscalation: (schoolId: string, escalationId: number, resolvedBy: string) =>
    post<TeacherEscalation>(`/schools/${schoolId}/escalations/${escalationId}/resolve`, {
      resolved_by: resolvedBy,
    }),
  listParentReports: (schoolId: string, studentId: string) =>
    get<ParentReport[]>(`/schools/${schoolId}/students/${studentId}/parent-reports`),
  createParentReport: (
    schoolId: string,
    body: {
      student_id: string
      sub_skill_id: string
      sub_skill_name_plain: string
      at_home_actions: string[]
    },
  ) => post<ParentReport>(`/schools/${schoolId}/parent-reports`, body),
}
