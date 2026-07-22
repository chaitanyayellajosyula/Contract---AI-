import { useEffect, useState } from 'react'
import { fetchCompanies } from '../lib/api'

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<any[]>([])

  useEffect(() => {
    async function loadCompanies() {
      try {
        const data = await fetchCompanies()
        setCompanies(data || [])
      } catch {
        setCompanies([])
      }
    }

    void loadCompanies()
  }, [])

  return (
    <div className="space-y-4 rounded-3xl border border-slate-800 bg-slate-900/70 p-6">
      <h1 className="text-2xl font-semibold text-white">Companies</h1>
      {companies.length === 0 ? (
        <p className="text-sm text-slate-400">No companies found.</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {companies.map((company) => (
            <div key={company.id} className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
              <p className="font-medium text-white">{company.name || '—'}</p>
              <p className="mt-1 text-sm text-slate-400">{company.website || '—'}</p>
              <p className="mt-1 text-sm text-slate-400">{company.industry || '—'}</p>
              <p className="mt-1 text-sm text-slate-400">{company.location || '—'}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
