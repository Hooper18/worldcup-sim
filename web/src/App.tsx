import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from './components/layout/AppShell'
import Dashboard from './pages/Dashboard'
import GroupsOverview from './pages/GroupsOverview'
import GroupDetail from './pages/GroupDetail'
import BracketPage from './pages/BracketPage'
import MatchDetail from './pages/MatchDetail'
import Schedule from './pages/Schedule'
import Trends from './pages/Trends'
import ModelPage from './pages/ModelPage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Dashboard />} />
        <Route path="groups" element={<GroupsOverview />} />
        <Route path="groups/:id" element={<GroupDetail />} />
        <Route path="schedule" element={<Schedule />} />
        <Route path="bracket" element={<BracketPage />} />
        <Route path="match/:id" element={<MatchDetail />} />
        <Route path="trends" element={<Trends />} />
        <Route path="model" element={<ModelPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
