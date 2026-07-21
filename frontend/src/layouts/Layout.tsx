import { Outlet } from 'react-router-dom'
import Header from '../components/Header'
import Sidebar from '../components/Sidebar'

export default function Layout() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex-1">
          <Header />
          <main className="p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  )
}
