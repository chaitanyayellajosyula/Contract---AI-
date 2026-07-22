import { useEffect, useState } from 'react'
import { fetchCompanies, fetchJobs, fetchVendorContacts, fetchVendors } from '../lib/api'

const initialCards = [
  { title: 'Companies', value: '0' },
  { title: 'Vendors', value: '0' },
  { title: 'Vendor Contacts', value: '0' },
  { title: 'Jobs', value: '0' },
]

export default function DashboardCards() {
  const [counts, setCounts] = useState(initialCards)

  useEffect(() => {
    async function loadCounts() {
      try {
        const [companies, vendors, contacts, jobs] = await Promise.all([
          fetchCompanies(),
          fetchVendors(),
          fetchVendorContacts(),
          fetchJobs(),
        ])

        setCounts([
          { title: 'Companies', value: String(companies?.length ?? 0) },
          { title: 'Vendors', value: String(vendors?.length ?? 0) },
          { title: 'Vendor Contacts', value: String(contacts?.length ?? 0) },
          { title: 'Jobs', value: String(jobs?.length ?? 0) },
        ])
      } catch {
        setCounts(initialCards)
      }
    }

    void loadCounts()
  }, [])

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {counts.map((card) => (
        <div key={card.title} className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-sm">
          <p className="text-sm text-slate-400">{card.title}</p>
          <p className="mt-3 text-3xl font-semibold text-white">{card.value}</p>
        </div>
      ))}
    </div>
  )
}
