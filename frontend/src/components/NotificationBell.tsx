import { Bell } from 'lucide-react'

export default function NotificationBell() {
  return (
    <button className="rounded-full border border-slate-800 p-2 text-slate-300 transition hover:bg-slate-800">
      <Bell className="h-4 w-4" />
    </button>
  )
}
