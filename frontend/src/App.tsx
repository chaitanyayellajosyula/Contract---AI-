import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import Layout from './layouts/Layout'
import LoginPage from './pages/LoginPage'
import MissionControlPage from './pages/MissionControlPage'
import JobsPage from './pages/JobsPage'
import VendorsPage from './pages/VendorsPage'
import RecruitersPage from './pages/RecruitersPage'
import ResumeAIPage from './pages/ResumeAIPage'
import AnalyticsPage from './pages/AnalyticsPage'
import SettingsPage from './pages/SettingsPage'
import CompaniesPage from './pages/CompaniesPage'
import SubmissionsPage from './pages/SubmissionsPage'

const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <MissionControlPage /> },
      { path: 'jobs', element: <JobsPage /> },
      { path: 'submissions', element: <SubmissionsPage /> },
      { path: 'companies', element: <CompaniesPage /> },
      { path: 'vendors', element: <VendorsPage /> },
      { path: 'recruiters', element: <RecruitersPage /> },
      { path: 'resume-ai', element: <ResumeAIPage /> },
      { path: 'analytics', element: <AnalyticsPage /> },
      { path: 'settings', element: <SettingsPage /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
