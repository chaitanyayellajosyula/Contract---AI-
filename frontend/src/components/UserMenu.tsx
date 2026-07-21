import { User } from 'lucide-react'

export default function UserMenu() {
  return (
    <div className="flex items-center gap-2 rounded-full border border-slate-800 bg-slate-950/70 px-3 py-2">
      <User className="h-4 w-4 text-slate-400" />
      <span className="text-sm text-slate-300">Admin</span>
    </div>
  )
}
