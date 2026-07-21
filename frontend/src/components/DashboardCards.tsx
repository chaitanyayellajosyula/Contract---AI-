const cards = [
  { title: 'Active Workspaces', value: '0' },
  { title: 'Live Opportunities', value: '0' },
  { title: 'Recruiter Outreach', value: '0' },
]

export default function DashboardCards() {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {cards.map((card) => (
        <div key={card.title} className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-sm">
          <p className="text-sm text-slate-400">{card.title}</p>
          <p className="mt-3 text-3xl font-semibold text-white">{card.value}</p>
        </div>
      ))}
    </div>
  )
}
