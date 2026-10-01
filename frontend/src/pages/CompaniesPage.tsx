import { useEffect, useState, type FormEvent } from 'react'
import { Building2, ChevronLeft, ChevronRight, ExternalLink, Search } from 'lucide-react'
import {
  fetchCompanyIntelligence,
  fetchCompanyIntelligenceJobs,
  searchCompanyIntelligence,
  type CompanyIntelligenceItem,
  type CompanyIntelligenceProfile,
  type IntelligenceJob,
} from '../lib/api'

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleDateString() : 'No activity yet'
}

function safeWebsite(value: string | null) {
  if (!value) return null
  try {
    const url = new URL(value.includes('://') ? value : `https://${value}`)
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.toString() : null
  } catch {
    return null
  }
}

export default function CompaniesPage() {
  const [input, setInput] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [companies, setCompanies] = useState<CompanyIntelligenceItem[]>([])
  const [total, setTotal] = useState(0)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [profile, setProfile] = useState<CompanyIntelligenceProfile | null>(null)
  const [jobs, setJobs] = useState<IntelligenceJob[]>([])
  const [jobPage, setJobPage] = useState(1)
  const [jobTotal, setJobTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    searchCompanyIntelligence(query, page, 20)
      .then((result) => {
        if (!active) return
        setCompanies(result.items)
        setTotal(result.total)
        setSelectedId((selected) => result.items.some((company) => company.id === selected)
          ? selected
          : result.items[0]?.id ?? null)
        setError('')
      })
      .catch(() => { if (active) setError('Company intelligence is unavailable for your account.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [query, page])

  useEffect(() => {
    if (selectedId === null) {
      setProfile(null)
      setJobs([])
      setJobTotal(0)
      return
    }
    let active = true
    setDetailLoading(true)
    setJobPage(1)
    fetchCompanyIntelligence(selectedId)
      .then((result) => { if (active) setProfile(result) })
      .catch(() => { if (active) setError('This company profile could not be loaded.') })
      .finally(() => { if (active) setDetailLoading(false) })
    return () => { active = false }
  }, [selectedId])

  useEffect(() => {
    if (selectedId === null) return
    let active = true
    fetchCompanyIntelligenceJobs(selectedId, { page: jobPage, page_size: 10 })
      .then((result) => {
        if (!active) return
        setJobs(result.items)
        setJobTotal(result.total)
      })
      .catch(() => { if (active) setError('Company jobs could not be loaded.') })
    return () => { active = false }
  }, [selectedId, jobPage])

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPage(1)
    setQuery(input.trim())
  }

  const companyWebsite = profile ? safeWebsite(profile.company.website) : null

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <p className="text-sm font-medium text-cyan-400">Relationships</p>
          <h1 className="mt-1 text-2xl font-semibold text-white">Company intelligence</h1>
        </div>
        <form className="flex w-full max-w-lg gap-2" onSubmit={submitSearch}>
          <label className="sr-only" htmlFor="company-search">Search companies</label>
          <input
            id="company-search"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Company, domain, or contact"
            className="min-w-0 flex-1 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500"
          />
          <button className="inline-flex items-center gap-2 rounded-md bg-cyan-700 px-3 py-2 text-sm font-medium text-white hover:bg-cyan-600" type="submit">
            <Search size={16} aria-hidden="true" /> Search
          </button>
        </form>
      </header>

      {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}

      <div className="grid gap-6 xl:grid-cols-[minmax(250px,0.75fr)_minmax(0,2fr)]">
        <section aria-label="Companies" className="min-w-0">
          <div className="mb-2 flex items-center justify-between text-sm text-slate-400">
            <span>{total} companies</span><span>Page {page}</span>
          </div>
          <div className="divide-y divide-slate-800 border-y border-slate-800">
            {loading ? <p className="py-4 text-sm text-slate-400">Loading companies…</p> : companies.length === 0 ? (
              <p className="py-4 text-sm text-slate-400">No companies found.</p>
            ) : companies.map((company) => (
              <button
                key={company.id}
                type="button"
                onClick={() => setSelectedId(company.id)}
                aria-pressed={selectedId === company.id}
                className={`block w-full px-3 py-3 text-left ${selectedId === company.id ? 'bg-slate-800/70' : 'hover:bg-slate-900'}`}
              >
                <span className="block truncate font-medium text-white">{company.name}</span>
                <span className="mt-1 block truncate text-xs text-slate-400">{company.website || company.industry || 'Company details not recorded'}</span>
                <span className="mt-2 flex gap-4 text-xs text-slate-500">
                  <span>{company.job_count} jobs</span><span>{company.vendor_count} vendors</span><span>{company.contact_count} contacts</span>
                </span>
              </button>
            ))}
          </div>
          <div className="mt-3 flex justify-between">
            <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} aria-label="Previous company page" className="rounded p-2 text-slate-300 hover:bg-slate-800 disabled:opacity-30"><ChevronLeft size={18} /></button>
            <button type="button" disabled={page * 20 >= total} onClick={() => setPage((value) => value + 1)} aria-label="Next company page" className="rounded p-2 text-slate-300 hover:bg-slate-800 disabled:opacity-30"><ChevronRight size={18} /></button>
          </div>
        </section>

        <section aria-label="Company profile" className="min-w-0">
          {detailLoading ? <p className="text-sm text-slate-400">Loading profile…</p> : !profile ? (
            <p className="border-y border-slate-800 py-8 text-sm text-slate-400">Select a company to see its profile.</p>
          ) : (
            <div className="space-y-6">
              <header className="border-b border-slate-800 pb-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-xl font-semibold text-white">{profile.company.name}</h2>
                    <p className="mt-1 text-sm text-slate-400">{[profile.company.industry, profile.company.location].filter(Boolean).join(' · ') || 'Company details not recorded'}</p>
                  </div>
                  {profile.company.website && (companyWebsite ? (
                    <a href={companyWebsite} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 break-all text-sm text-cyan-300 hover:text-cyan-200"><Building2 size={15} />{profile.company.website}<ExternalLink size={13} /></a>
                  ) : <span className="text-sm text-slate-400">{profile.company.website}</span>)}
                </div>
              </header>

              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Metric label="Jobs" value={profile.summary.total_jobs} />
                <Metric label="Recent jobs" value={profile.summary.recent_jobs} />
                <Metric label="Vendors" value={profile.company.vendor_count} />
                <Metric label="Latest activity" value={formatDate(profile.company.latest_activity)} />
              </div>

              <div className="grid gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(240px,0.8fr)]">
                <section>
                  <div className="mb-3 flex items-center justify-between">
                    <h3 className="font-medium text-white">Associated jobs</h3>
                    <span className="text-xs text-slate-500">{jobTotal} total</span>
                  </div>
                  <div className="divide-y divide-slate-800 border-y border-slate-800">
                    {jobs.length === 0 ? <p className="py-4 text-sm text-slate-400">No associated jobs.</p> : jobs.map((job) => (
                      <JobRow key={job.id} job={job} />
                    ))}
                  </div>
                  <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                    <span>Page {jobPage} of {Math.max(1, Math.ceil(jobTotal / 10))}</span>
                    <div className="flex gap-1">
                      <button type="button" disabled={jobPage <= 1} onClick={() => setJobPage((value) => value - 1)} aria-label="Previous job page" className="rounded p-2 text-slate-300 hover:bg-slate-800 disabled:opacity-30"><ChevronLeft size={16} /></button>
                      <button type="button" disabled={jobPage * 10 >= jobTotal} onClick={() => setJobPage((value) => value + 1)} aria-label="Next job page" className="rounded p-2 text-slate-300 hover:bg-slate-800 disabled:opacity-30"><ChevronRight size={16} /></button>
                    </div>
                  </div>
                </section>

                <div className="space-y-6">
                  <section>
                    <h3 className="mb-3 font-medium text-white">Known vendors</h3>
                    {profile.vendors.length === 0 ? <p className="text-sm text-slate-400">No vendors recorded.</p> : (
                      <ul className="divide-y divide-slate-800 border-y border-slate-800">
                        {profile.vendors.map((vendor) => <li key={vendor.id} className="py-3">
                          <p className="font-medium text-slate-200">{vendor.name}</p>
                          <p className="mt-1 text-xs text-slate-500">{vendor.job_count} jobs · {vendor.contact_count} contacts</p>
                          {vendor.email && <a href={`mailto:${vendor.email}`} className="mt-1 block break-all text-sm text-cyan-300">{vendor.email}</a>}
                        </li>)}
                      </ul>
                    )}
                  </section>
                  <section>
                    <h3 className="mb-3 font-medium text-white">Known contacts</h3>
                    {profile.contacts.length === 0 ? <p className="text-sm text-slate-400">No contacts recorded.</p> : (
                      <ul className="divide-y divide-slate-800 border-y border-slate-800">
                        {profile.contacts.map((contact) => <li key={contact.id} className="py-3">
                          <p className="font-medium text-slate-200">{contact.full_name}</p>
                          <a href={`mailto:${contact.email}`} className="mt-1 block break-all text-sm text-cyan-300">{contact.email}</a>
                          <p className="mt-1 text-xs text-slate-500">{contact.vendor_name} · {contact.designation || 'Role not recorded'}</p>
                        </li>)}
                      </ul>
                    )}
                  </section>
                  <section>
                    <h3 className="mb-2 font-medium text-white">Observed</h3>
                    <Fact label="Sources" values={profile.summary.sources} />
                    <Fact label="Engagement" values={profile.summary.engagement_types} />
                    <Fact label="Locations" values={profile.summary.locations} />
                    <p className="mt-3 text-xs text-slate-500">First job activity {formatDate(profile.summary.first_observed_job_activity)}</p>
                  </section>
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return <div className="min-w-0 border-l-2 border-cyan-800 py-1 pl-3">
    <p className="text-xs text-slate-500">{label}</p>
    <p className="mt-1 truncate text-sm font-medium text-slate-100">{value}</p>
  </div>
}

function Fact({ label, values }: { label: string; values: string[] }) {
  return <div className="py-2">
    <p className="text-xs text-slate-500">{label}</p>
    <p className="mt-1 text-sm text-slate-300">{values.length ? values.join(', ') : 'No data'}</p>
  </div>
}

function JobRow({ job }: { job: IntelligenceJob }) {
  return <article className="py-3">
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="font-medium text-slate-200">{job.external_url ? <a href={job.external_url} target="_blank" rel="noreferrer" className="hover:text-cyan-300">{job.title}</a> : job.title}</p>
        <p className="mt-1 text-xs text-slate-500">{[job.source_company, job.location, job.employment_type, job.source].filter(Boolean).join(' · ') || 'No additional details'}</p>
      </div>
      <time className="shrink-0 text-xs text-slate-500">{formatDate(job.posted_at || job.created_at)}</time>
    </div>
    {(job.viewed || job.saved || job.hidden) && <p className="mt-1 text-xs text-slate-500">{[job.viewed && 'Viewed', job.saved && 'Saved', job.hidden && 'Hidden'].filter(Boolean).join(' · ')}</p>}
  </article>
}
