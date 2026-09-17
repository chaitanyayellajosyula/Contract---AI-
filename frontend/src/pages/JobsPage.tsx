import { useEffect, useState } from 'react'
import { Bookmark, BriefcaseBusiness, ChevronLeft, ChevronRight, ExternalLink, Eye, EyeOff, MapPin, Search, X } from 'lucide-react'
import { ApiError, fetchJobs, Job, JobFilters, updateJobStatus } from '../lib/api'

const PAGE_SIZE = 20

function freshness(date: string | null) {
  if (!date) return 'Date unknown'
  const days = Math.floor((Date.now() - new Date(date).getTime()) / 86400000)
  if (days <= 0) return 'Today'
  if (days === 1) return 'Yesterday'
  return `${days}d ago`
}

function label(value: string | null) {
  if (!value) return 'Not specified'
  return value.replace(/_/g, ' ')
}

function JobDetail({ job, onClose, onStatus }: { job: Job; onClose: () => void; onStatus: (updates: { viewed?: boolean; saved?: boolean; hidden?: boolean }) => void }) {
  return (
    <aside className="flex h-full min-h-[520px] flex-col border-l border-slate-800 bg-slate-950/90 p-6 lg:sticky lg:top-6 lg:max-h-[calc(100vh-3rem)] lg:overflow-y-auto">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-cyan-400">Opportunity detail</p>
          <h2 className="text-xl font-semibold leading-tight text-white">{job.title}</h2>
          <p className="mt-2 text-sm text-slate-400">{job.company || job.source_company || 'Company not specified'}</p>
        </div>
        <button aria-label="Close details" title="Close details" onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white"><X size={18} /></button>
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div><p className="text-xs uppercase tracking-wide text-slate-500">Source</p><p className="mt-1 text-slate-200">{job.source || 'Unknown'}</p></div>
        <div><p className="text-xs uppercase tracking-wide text-slate-500">Freshness</p><p className="mt-1 text-cyan-300">{freshness(job.posted_at)}</p></div>
        <div><p className="text-xs uppercase tracking-wide text-slate-500">Location</p><p className="mt-1 text-slate-200">{job.location || 'Not specified'}</p></div>
        <div><p className="text-xs uppercase tracking-wide text-slate-500">Arrangement</p><p className="mt-1 text-slate-200">{label(job.remote_type)}</p></div>
        <div><p className="text-xs uppercase tracking-wide text-slate-500">Engagement</p><p className="mt-1 text-slate-200">{label(job.employment_type)}</p></div>
        <div><p className="text-xs uppercase tracking-wide text-slate-500">Posted</p><p className="mt-1 text-slate-200">{job.posted_at ? new Date(job.posted_at).toLocaleString() : 'Not specified'}</p></div>
      </div>

      <div className="mt-6 flex flex-wrap gap-2">
        <button onClick={() => onStatus({ saved: !job.saved })} className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${job.saved ? 'border-amber-400/50 bg-amber-400/10 text-amber-300' : 'border-slate-700 text-slate-300 hover:border-slate-500'}`}><Bookmark size={16} fill={job.saved ? 'currentColor' : 'none'} />{job.saved ? 'Saved' : 'Save job'}</button>
        <button onClick={() => onStatus({ hidden: !job.hidden })} className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 hover:border-slate-500">{job.hidden ? <Eye size={16} /> : <EyeOff size={16} />}{job.hidden ? 'Unhide' : 'Hide'}</button>
      </div>

      <div className="mt-6 flex gap-2">
        {job.apply_url && <a href={job.apply_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-lg bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-300">Apply <ExternalLink size={15} /></a>}
        {job.source_url && <a href={job.source_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-200 hover:border-slate-500">View source <ExternalLink size={15} /></a>}
      </div>

      <section className="mt-7 border-t border-slate-800 pt-6">
        <h3 className="text-sm font-semibold text-white">Description</h3>
        <div className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-300">{job.description || 'No description provided by the source.'}</div>
      </section>
      {job.source_job_id && <p className="mt-6 border-t border-slate-800 pt-4 text-xs text-slate-500">Source job ID: {job.source_job_id}</p>}
    </aside>
  )
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [selected, setSelected] = useState<Job | null>(null)
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({ search: '', engagement: '', arrangement: '', location: '', source: '', company: '', freshness: '' })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const query: JobFilters = {
        title: filters.search || undefined,
        engagement: filters.engagement || undefined,
        remote_type: filters.arrangement || undefined,
        location: filters.location || undefined,
        source: filters.source || undefined,
        company: filters.company || undefined,
        freshness: filters.freshness || undefined,
        hidden: false,
        page,
        page_size: PAGE_SIZE,
      }
      setLoading(true)
      void fetchJobs(query).then((data) => {
        setJobs(data)
        if (selected && !data.some((job) => job.id === selected.id)) setSelected(null)
        setError('')
      }).catch(() => setError('Unable to load opportunities. Check that the API is available.')).finally(() => setLoading(false))
    }, 180)
    return () => window.clearTimeout(timer)
  }, [filters, page])

  function changeFilter(key: keyof typeof filters, value: string) {
    setPage(1)
    setFilters((current) => ({ ...current, [key]: value }))
  }

  async function markStatus(updates: { viewed?: boolean; saved?: boolean; hidden?: boolean }) {
    if (!selected) return
    try {
      const updated = await updateJobStatus(selected.id, updates)
      setSelected(updated)
      setJobs((current) => current.map((job) => job.id === updated.id ? updated : job).filter((job) => !job.hidden))
    } catch (statusError) {
      if (statusError instanceof ApiError && statusError.status === 401) setError('Sign in to save, hide, or mark opportunities viewed.')
      else setError('Unable to update this opportunity.')
    }
  }

  async function openJob(job: Job) {
    setSelected(job)
    if (!job.viewed) {
      try {
        const updated = await updateJobStatus(job.id, { viewed: true })
        setSelected(updated)
        setJobs((current) => current.map((item) => item.id === updated.id ? updated : item))
      } catch {
        // Public browsing remains available when the viewer is not authenticated.
      }
    }
  }

  const canGoNext = jobs.length === PAGE_SIZE

  return (
    <div className="space-y-5">
      <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-400">Opportunity desk</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white">Job Hunter</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-400">Fresh public opportunities, organized for fast recruiter triage.</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-slate-400"><BriefcaseBusiness size={17} className="text-cyan-400" /> Newest opportunities first</div>
      </header>

      <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 shadow-2xl shadow-slate-950/20">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <label className="relative md:col-span-2"><Search size={17} className="absolute left-3 top-3 text-slate-500" /><input value={filters.search} onChange={(event) => changeFilter('search', event.target.value)} placeholder="Search title or keyword" className="w-full rounded-xl border border-slate-700 bg-slate-950 px-10 py-2.5 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-400" /></label>
          <select value={filters.engagement} onChange={(event) => changeFilter('engagement', event.target.value)} className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-cyan-400"><option value="">All engagements</option><option value="contract">Contract</option><option value="contract_to_hire">C2H</option><option value="c2c">C2C</option><option value="w2">W2</option><option value="full_time">Full-time</option><option value="internship">Internship</option></select>
          <select value={filters.arrangement} onChange={(event) => changeFilter('arrangement', event.target.value)} className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-cyan-400"><option value="">All arrangements</option><option value="remote">Remote</option><option value="hybrid">Hybrid</option><option value="on-site">On-site</option></select>
          <input value={filters.location} onChange={(event) => changeFilter('location', event.target.value)} placeholder="Location" className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-400" />
          <input value={filters.company} onChange={(event) => changeFilter('company', event.target.value)} placeholder="Company" className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-400" />
          <input value={filters.source} onChange={(event) => changeFilter('source', event.target.value)} placeholder="Source" className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white outline-none placeholder:text-slate-600 focus:border-cyan-400" />
          <select value={filters.freshness} onChange={(event) => changeFilter('freshness', event.target.value)} className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-cyan-400"><option value="">Any freshness</option><option value="today">Today</option><option value="last_3_days">Last 3 days</option><option value="last_7_days">Last 7 days</option><option value="older">Older</option></select>
        </div>
      </section>

      {error && <div className="rounded-xl border border-rose-400/30 bg-rose-400/10 px-4 py-3 text-sm text-rose-200">{error}</div>}
      <div className={`grid gap-5 ${selected ? 'lg:grid-cols-[minmax(0,1fr)_420px]' : ''}`}>
        <section className="min-w-0 rounded-2xl border border-slate-800 bg-slate-900/60">
          <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4"><div><h2 className="font-semibold text-white">Open opportunities</h2><p className="mt-1 text-xs text-slate-500">Page {page} · {jobs.length} loaded</p></div><div className="flex gap-1"><button disabled={page === 1} onClick={() => setPage((value) => value - 1)} aria-label="Previous page" title="Previous page" className="rounded-lg p-2 text-slate-400 enabled:hover:bg-slate-800 enabled:hover:text-white disabled:opacity-30"><ChevronLeft size={18} /></button><button disabled={!canGoNext} onClick={() => setPage((value) => value + 1)} aria-label="Next page" title="Next page" className="rounded-lg p-2 text-slate-400 enabled:hover:bg-slate-800 enabled:hover:text-white disabled:opacity-30"><ChevronRight size={18} /></button></div></div>
          {loading ? <div className="px-5 py-12 text-center text-sm text-slate-500">Loading opportunities...</div> : jobs.length === 0 ? <div className="px-5 py-12 text-center text-sm text-slate-500">No opportunities match these filters.</div> : <div className="divide-y divide-slate-800/80">{jobs.map((job) => <button key={job.id} onClick={() => void openJob(job)} className={`block w-full px-5 py-4 text-left transition hover:bg-slate-800/50 ${selected?.id === job.id ? 'bg-cyan-400/5' : ''}`}><div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between"><div className="min-w-0"><div className="flex items-center gap-2"><h3 className="truncate font-semibold text-white">{job.title}</h3>{!job.viewed && <span className="rounded-full bg-cyan-400/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-cyan-300">New</span>}</div><p className="mt-1 text-sm text-slate-400">{job.company || job.source_company || 'Company not specified'}</p><div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400"><span className="inline-flex items-center gap-1"><MapPin size={13} />{job.location || 'Location unknown'}</span><span className="rounded bg-slate-800 px-2 py-1">{label(job.remote_type)}</span><span className="rounded bg-slate-800 px-2 py-1">{label(job.employment_type)}</span><span className="rounded bg-slate-800 px-2 py-1">{job.source || 'Unknown source'}</span></div></div><div className="flex shrink-0 items-center gap-3 text-xs text-slate-500"><span className={job.posted_at && freshness(job.posted_at).includes('Today') ? 'font-semibold text-cyan-300' : ''}>{freshness(job.posted_at)}</span>{job.saved && <Bookmark size={15} className="text-amber-300" fill="currentColor" />}</div></div></button>)}</div>}
        </section>
        {selected && <JobDetail job={selected} onClose={() => setSelected(null)} onStatus={(updates) => void markStatus(updates)} />}
      </div>
    </div>
  )
}