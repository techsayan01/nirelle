# Nirelle frontend

React + TypeScript + Vite + Tailwind CSS v4, talking to the `nirelle` API
(see [`../README.md`](../README.md)). Covers the student, teacher, and
parent views from the BRD, against the hand-built Grade 4 Math (fractions)
demo content.

## Design approach

Before building this, we looked at IXL and Khan Academy's actual practice
UI (not just marketing pages) and checked Apple HIG / Material Design
conventions via the `ui-ux-pro-max` skill. The key finding: credible K-12
products use **one consistent UI system across every grade** and
differentiate by accent color, copy tone, and density - not by re-skinning
the whole interface per age group. Doing the latter is what tends to read
as disjointed/AI-generated rather than as one coherent product.

So there's one component system, one icon family (Phosphor, weight varies
by band), and one type family (Plus Jakarta Sans; Fredoka only for
elementary's big celebratory headlines) - and grade bands differ through:

- **Color** - blue/amber/pink (elementary) → teal/cyan (middle) →
  indigo/slate (high school + teacher/parent, always "high" regardless of
  the student's own grade).
- **Corner radius** - 20-28px (elementary, huggable) down to 8-16px (high
  school, crisper/more "productivity tool").
- **Motion intensity** - confetti + mascot (elementary) → checkmark pop
  (middle) → plain checkmark fade (high school) on reaching mastery.
- **Copy tone**, not vocabulary - the underlying flow and terminology stay
  the same at every grade.

All of this is CSS custom properties (`src/theme/tokens.css`) switched by
a single `[data-band]` attribute (`src/theme/useAppBand.ts`), never
per-component branching on grade - components only ever reference
Tailwind's semantic utilities (`bg-primary`, `rounded-md`, ...).

## Layout

- `src/theme/` - design tokens, grade→band mapping (`bands.ts`), the
  `useAppBand` hook that pages call to set the active theme.
- `src/api/` - typed `fetch` client (`client.ts`) and response types
  (`types.ts`) for the backend; `/api/*` is proxied to `localhost:8000` in
  dev (see `vite.config.ts`).
- `src/components/` - shared UI: `Button`, `Card`, `AppShell`,
  `MasteryMeter`, `QuestionFlow` (the interactive question/answer flow,
  response-time-timed), `FractionBar` (the BRD's "auto-generated SVG
  visual" - a segmented bar; handles improper fractions like a
  numerator/denominator-swap wrong answer by drawing whole bars + a
  remainder bar rather than an uninformative solid block), `Celebration`
  (band-appropriate success motion), `Mascot` (a single restrained
  geometric mark, elementary-only).
- `src/pages/`:
  - `Landing.tsx` - role (student/teacher/parent) and grade picker, with
    a **live theme preview** as you pick a grade. Creates/resumes the
    demo school and student.
  - `StudentHome.tsx` - available sub-skills for the student's grade
    (with an honest empty state for every grade but 4, since that's all
    the demo curriculum covers) and each one's mastery meter.
  - `PracticeSession.tsx` - the full loop: diagnostic → misconception
    identified → personalized remediation → re-test → resolved
    /escalated, looping back to a fresh diagnostic round when still below
    floor with cycles left (matches the BRD flowchart exactly) - plus the
    `teacher_retest` stage's one-question check-in after a teacher
    resolves a case.
  - `TeacherDashboard.tsx` / `TeacherEscalationDetail.tsx` - flagged
    students, case detail (misconception, what's been tried, 1-on-1
    focus), and the "mark resolved" action, which both closes the
    escalation report and advances the student's mastery-state loop.
  - `ParentView.tsx` - the separate, plain-language parent report.
- `src/state/SessionProvider.tsx` - the demo's only "auth": a
  `localStorage`-backed role/school/student identity, since there's no
  login system yet (see the main README's open items).

## Running it

```bash
# backend, from the repo root
pip install -e ".[api]"
python -m nirelle.api          # http://localhost:8000, auto-seeds demo curriculum

# frontend, from this directory
npm install
npm run dev                    # http://localhost:5173, proxies /api -> :8000
```

## Development

```bash
npm run build   # tsc -b && vite build - type-checks and bundles
npm run lint    # oxlint
```

There's no frontend test suite yet - this was verified by driving the
running app end-to-end (all three roles, the full escalation loop,
mobile viewport, empty states) rather than with component tests. Worth
adding before this goes further than a demo.
