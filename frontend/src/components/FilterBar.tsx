export default function FilterBar() {
  return (
    <div className="flex flex-wrap gap-3">
      <button className="rounded-full border border-slate-700 px-3 py-2 text-sm text-slate-300">All</button>
      <button className="rounded-full border border-slate-700 px-3 py-2 text-sm text-slate-300">Recent</button>
      <button className="rounded-full border border-slate-700 px-3 py-2 text-sm text-slate-300">Priority</button>
    </div>
  )
}
