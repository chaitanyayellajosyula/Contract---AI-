import { useEffect, useState, type FormEvent } from 'react'
import { ChevronLeft, ChevronRight, Search } from 'lucide-react'
import {
  fetchCandidateHotlist,
  fetchSubmissions,
  type CandidateHotlistItem,
  type Submission,
} from '../lib/api'

const PAGE_SIZE = 25

const emptyFilters = {
  q: '',
  location: '',
  experience: '',
  visa_status: '',
  availability_status: '',
  rate: '',
}

function display(value: string | null) {
  return value?.trim() || 'Not recorded'
}

export default function CandidatesPage() {
  const [inputs, setInputs] = useState(emptyFilters)
  const [filters, setFilters] = useState(emptyFilters)
  const [page, setPage] = useState(1)
  const [items, setItems] = useState<CandidateHotlistItem[]>([])
  const [total, setTotal] = useState(0)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [submissions, setSubmissions] = useState<Submission[]>([])
  const [loading, setLoading] = useState(true)
  const [submissionsLoading, setSubmissionsLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    fetchCandidateHotlist({ ...filters, page, page_size: PAGE_SIZE })
      .then((result) => {
        if (!active) return
        setItems(result.items)
        setTotal(result.total)
        setSelectedId((current) => result.items.some((item) => item.candidate.id === current)
          ? current
          : result.items[0]?.candidate.id ?? null)
        setError('')
      })
      .catch(() => { if (active) setError('Candidate hotlist is unavailable for your account.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [filters, page])

  useEffect(() => {
    if (selectedId === null) {
      setSubmissions([])
      return
    }
    let active = true
    setSubmissionsLoading(true)
    fetchSubmissions({ candidateId: selectedId })
      .then((result) => { if (active) setSubmissions(result) })
      .catch(() => { if (active) setSubmissions([]) })
      .finally(() => { if (active) setSubmissionsLoading(false) })
    return () => { active = false }
  }, [selectedId])

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPage(1)
    setFilters({ ...inputs })
  }

  const selected = items.find((item) => item.candidate.id === selectedId) ?? null

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <p className="text-sm font-medium text-cyan-400">Recruiting</p>
          <h1 className="mt-1 text-2xl font-semibold text-white">Candidate hotlist</h1>
          <p className="mt-1 text-sm text-slate-400">Search only candidates available to your account.</p>
        </div>
        <span className="text-sm text-slate-400">{total} candidates</span>
      </header>

      <form onSubmit={search} className="grid gap-2 border-b border-slate-800 pb-4 md:grid-cols-3 xl:grid-cols-6">
        <label className="relative md:col-span-2 xl:col-span-2">
          <span className="sr-only">Candidate name</span>
          <Search size={16} className="absolute left-3 top-3 text-slate-500" />
          <input aria-label="Name or email" value={inputs.q} onChange={(event) => setInputs({ ...inputs, q: event.target.value })} placeholder="Name or email" className="w-full rounded-md border border-slate-700 bg-slate-900 py-2 pl-9 pr-3 text-sm text-white outline-none focus:border-cyan-500" />
        </label>
        <input aria-label="Location" value={inputs.location} onChange={(event) => setInputs({ ...inputs, location: event.target.value })} placeholder="Location" className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500" />
        <input aria-label="Experience" value={inputs.experience} onChange={(event) => setInputs({ ...inputs, experience: event.target.value })} placeholder="Experience" className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500" />
        <input aria-label="Visa or work authorization" value={inputs.visa_status} onChange={(event) => setInputs({ ...inputs, visa_status: event.target.value })} placeholder="Visa / authorization" className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500" />
        <input aria-label="Availability status" value={inputs.availability_status} onChange={(event) => setInputs({ ...inputs, availability_status: event.target.value })} placeholder="Availability" className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500" />
        <input aria-label="Current or expected rate" value={inputs.rate} onChange={(event) => setInputs({ ...inputs, rate: event.target.value })} placeholder="Current / expected rate" className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-500" />
        <button type="submit" className="inline-flex items-center justify-center gap-2 rounded-md bg-cyan-700 px-3 py-2 text-sm font-medium text-white hover:bg-cyan-600 md:col-start-3 xl:col-start-6"><Search size={16} />Search</button>
      </form>

      {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}

      <div className="grid gap-6 xl:grid-cols-[minmax(260px,0.8fr)_minmax(0,2fr)]">
        <section aria-label="Candidates">
          <div className="divide-y divide-slate-800 border-y border-slate-800">
            {loading ? <p className="py-4 text-sm text-slate-400">Loading candidates…</p> : items.length === 0 ? (
              <p className="py-4 text-sm text-slate-400">No candidates match these filters.</p>
            ) : items.map((item) => (
              <button key={item.candidate.id} type="button" onClick={() => setSelectedId(item.candidate.id)} aria-pressed={selectedId === item.candidate.id} className={`block w-full px-3 py-3 text-left ${selectedId === item.candidate.id ? 'bg-slate-800/70' : 'hover:bg-slate-900'}`}>
                <span className="block truncate font-medium text-white">{item.candidate.first_name} {item.candidate.last_name}</span>
                <span className="mt-1 block text-xs text-slate-400">{item.candidate.current_location || item.candidate.preferred_location || 'Location not recorded'} · {item.candidate.total_experience || 'Experience not recorded'}</span>
                <span className="mt-1 block text-xs text-slate-500">{item.candidate.availability_status || 'Availability not recorded'}</span>
              </button>
            ))}
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
            <span>Page {page} of {Math.max(1, Math.ceil(total / PAGE_SIZE))}</span>
            <div className="flex gap-1">
              <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} aria-label="Previous candidate page" className="rounded p-2 text-slate-300 hover:bg-slate-800 disabled:opacity-30"><ChevronLeft size={17} /></button>
              <button type="button" disabled={page * PAGE_SIZE >= total} onClick={() => setPage((value) => value + 1)} aria-label="Next candidate page" className="rounded p-2 text-slate-300 hover:bg-slate-800 disabled:opacity-30"><ChevronRight size={17} /></button>
            </div>
          </div>
        </section>

        <section aria-label="Candidate details" className="min-w-0 border-t border-slate-800 pt-4 xl:border-l xl:border-t-0 xl:pl-6 xl:pt-0">
          {!selected ? <p className="py-6 text-sm text-slate-400">Select a candidate to review recorded information.</p> : (
            <div className="space-y-6">
              <header className="border-b border-slate-800 pb-4">
                <h2 className="text-xl font-semibold text-white">{selected.candidate.first_name} {selected.candidate.last_name}</h2>
                <p className="mt-1 break-all text-sm text-slate-400">{selected.candidate.email}</p>
              </header>
              <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
                <Fact label="Current location" value={selected.candidate.current_location} />
                <Fact label="Preferred location" value={selected.candidate.preferred_location} />
                <Fact label="Total experience" value={selected.candidate.total_experience} />
                <Fact label="US experience" value={selected.candidate.us_experience} />
                <Fact label="Visa / authorization" value={selected.candidate.visa_status} />
                <Fact label="Availability" value={selected.candidate.availability_status} />
                <Fact label="Current rate" value={selected.candidate.current_rate} />
                <Fact label="Expected rate" value={selected.candidate.expected_rate} />
                <Fact label="Resume filename" value={selected.candidate.resume_filename} />
              </dl>
              <section className="border-t border-slate-800 pt-4">
                <h3 className="font-medium text-white">Profile data availability</h3>
                <p className="mt-2 text-sm text-slate-400">Skills, title, education, certifications, and resume content are not stored in this profile. Missing fields are not inferred.</p>
                <p className="mt-2 text-xs text-slate-500">{Object.entries(selected.data_availability).filter(([, state]) => state === 'not_recorded').map(([field]) => field.replace(/_/g, ' ')).join(', ') || 'No supported fields are missing.'} {Object.entries(selected.data_availability).some(([, state]) => state === 'not_recorded') ? 'not recorded.' : ''}</p>
              </section>
              <section className="border-t border-slate-800 pt-4">
                <h3 className="font-medium text-white">Vendor and submission context</h3>
                {submissionsLoading ? <p className="mt-2 text-sm text-slate-400">Loading submissions…</p> : submissions.length === 0 ? (
                  <p className="mt-2 text-sm text-slate-400">No authorized submissions recorded.</p>
                ) : <ul className="mt-2 divide-y divide-slate-800 border-y border-slate-800">{submissions.map((submission) => (
                  <li key={submission.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
                    <div><p className="font-medium text-slate-200">{submission.job.title}</p><p className="mt-1 text-xs text-slate-500">{submission.vendor_name || submission.company.name} · {submission.company.name}</p></div>
                    <span className="text-xs text-cyan-300">{submission.status.replace(/_/g, ' ')}</span>
                  </li>
                ))}</ul>}
              </section>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function Fact({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-1 break-words text-sm text-slate-200">{display(value)}</dd>
    </div>
  )
}