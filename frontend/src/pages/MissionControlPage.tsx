import DashboardCards from '../components/DashboardCards'
import OpportunityTable from '../components/OpportunityTable'

export default function MissionControlPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-white">Mission Control</h1>
        <p className="mt-2 text-sm text-slate-400">Application shell ready for future product work.</p>
      </div>
      <DashboardCards />
      <OpportunityTable />
    </div>
  )
}
