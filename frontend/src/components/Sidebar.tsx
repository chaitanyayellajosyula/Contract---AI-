import { NavLink } from 'react-router-dom'

const items = [
  { to: '/', label: 'Mission Control' },
  { to: '/jobs', label: 'Live Opportunities' },
  { to: '/vendors', label: 'Vendors' },
  { to: '/recruiters', label: 'Recruiters' },
  { to: '/resume-ai', label: 'Resume AI' },
  { to: '/analytics', label: 'Analytics' },
  { to: '/settings', label: 'Settings' },
]

export default function Sidebar() {
  return (
    <aside className="w-72 border-r border-slate-800 bg-slate-900/80 p-6">
      <div className="mb-8">
        <p className="text-sm uppercase tracking-[0.3em] text-slate-400">Contract Hunter AI</p>
        <h2 className="mt-2 text-xl font-semibold">Application Foundation</h2>
      </div>
      <nav className="space-y-2">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center rounded-lg px-3 py-2 text-sm transition ${isActive ? 'bg-slate-800 text-white' : 'text-slate-400 hover:bg-slate-800/70 hover:text-white'}`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
