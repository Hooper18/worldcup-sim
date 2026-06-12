import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import Dashboard from './pages/Dashboard'
import GroupsOverview from './pages/GroupsOverview'
import GroupDetail from './pages/GroupDetail'
import BracketPage from './pages/BracketPage'
import Placeholder from './pages/Placeholder'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Dashboard />} />
        <Route path="groups" element={<GroupsOverview />} />
        <Route path="groups/:id" element={<GroupDetail />} />
        <Route path="bracket" element={<BracketPage />} />
        <Route path="match/:id" element={<Placeholder title="单场详情" />} />
        <Route path="trends" element={<Placeholder title="概率演变" />} />
        <Route path="model" element={<Placeholder title="模型说明" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
