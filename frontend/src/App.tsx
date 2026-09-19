import { BrowserRouter, Route, Routes } from "react-router-dom"
import Landing from "./pages/Landing"
import ParentView from "./pages/ParentView"
import PracticeSession from "./pages/PracticeSession"
import StudentHome from "./pages/StudentHome"
import TeacherDashboard from "./pages/TeacherDashboard"
import TeacherEscalationDetail from "./pages/TeacherEscalationDetail"
import { SessionProvider } from "./state/SessionProvider"

export default function App() {
  return (
    <SessionProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/student" element={<StudentHome />} />
          <Route path="/student/practice/:subSkillId" element={<PracticeSession />} />
          <Route path="/teacher" element={<TeacherDashboard />} />
          <Route path="/teacher/escalations/:escalationId" element={<TeacherEscalationDetail />} />
          <Route path="/parent" element={<ParentView />} />
        </Routes>
      </BrowserRouter>
    </SessionProvider>
  )
}
