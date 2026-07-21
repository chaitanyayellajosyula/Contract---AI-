import { Bell, Moon, Search, Settings, User } from 'lucide-react'

export default function Header() {
  return (
    <header className="border-b border-slate-800 bg-slate-900/80 px-6 py-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex flex-1 items-center gap-3 rounded-full border border-slate-800 bg-slate-950/70 px-4 py-2">
          <Search className="h-4 w-4 text-slate-400" />
          <input
            className="w-full bg-transparent text-sm outline-none placeholder:text-slate-500"
            placeholder="Search workspace"
          />
        </div>
        <div className="flex items-center gap-2">
          <button className="rounded-full border border-slate-800 p-2 text-slate-300 transition hover:bg-slate-800">
            <Moon className="h-4 w-4" />
          </button>
          <button className="rounded-full border border-slate-800 p-2 text-slate-300 transition hover:bg-slate-800">
            <Bell className="h-4 w-4" />
          </button>
          <button className="rounded-full border border-slate-800 p-2 text-slate-300 transition hover:bg-slate-800">
            <Settings className="h-4 w-4" />
          </button>
          <div className="flex items-center gap-2 rounded-full border border-slate-800 bg-slate-950/70 px-3 py-2">
            <User className="h-4 w-4 text-slate-400" />
            <span className="text-sm text-slate-300">Admin</span>
          </div>
        </div>
      </div>
    </header>
  )
}
