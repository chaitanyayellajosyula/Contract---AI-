import { Search } from 'lucide-react'

export default function SearchBar() {
  return (
    <div className="flex items-center gap-3 rounded-full border border-slate-800 bg-slate-950/70 px-4 py-2">
      <Search className="h-4 w-4 text-slate-400" />
      <input className="w-full bg-transparent text-sm outline-none placeholder:text-slate-500" placeholder="Search" />
    </div>
  )
}
