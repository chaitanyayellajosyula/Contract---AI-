import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, fetchSubmissions, Submission, submissionStatuses, SubmissionStatus, updateSubmission } from '../lib/api'

const nextStatuses: Record<SubmissionStatus, SubmissionStatus[]> = {
  SUBMITTED: ['REVIEWING', 'REJECTED'],
  REVIEWING: ['INTERVIEW', 'REJECTED'],
  INTERVIEW: ['PLACED', 'REJECTED'],
  REJECTED: [],
  PLACED: [],
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString()
}

export default function SubmissionsPage() {
  const [submissions, setSubmissions] = useState<Submission[]>([])
  const [status, setStatus] = useState<SubmissionStatus | ''>('')
  const [jobId, setJobId] = useState('')
  const [candidateId, setCandidateId] = useState('')
  const [notes, setNotes] = useState<Record<number, string>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [unauthorized, setUnauthorized] = useState(false)

  async function loadSubmissions() {
    setLoading(true)
    setError('')
    try {
      const data = await fetchSubmissions({
        status: status || undefined,
        jobId: jobId ? Number(jobId) : undefined,
        candidateId: candidateId ? Number(candidateId) : undefined,
      })
      setSubmissions(data)
      setNotes(Object.fromEntries(data.map((submission) => [submission.id, submission.notes || ''])))
      setUnauthorized(false)
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) setUnauthorized(true)
      else setError('Submissions could not be loaded.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void loadSubmissions() }, [status, jobId, candidateId])

  async function changeSubmission(submission: Submission, nextStatus: SubmissionStatus) {
    try {
      const updated = await updateSubmission(submission.id, { status: nextStatus })
      setSubmissions((current) => current.map((item) => item.id === updated.id ? updated : item))
    } catch {
      setError('The submission status could not be updated.')
    }
  }

  async function saveNotes(submission: Submission) {
    try {
      const updated = await updateSubmission(submission.id, { notes: notes[submission.id] || '' })
      setSubmissions((current) => current.map((item) => item.id === updated.id ? updated : item))
    } catch {
      setError('The submission notes could not be updated.')
    }
  }

  if (unauthorized) return <div className="space-y-4 rounded-3xl border border-slate-800 bg-slate-900/70 p-6"><h1 className="text-2xl font-semibold text-white">Sign-in required</h1><p className="text-slate-400">Your session is missing or has expired.</p><Link className="inline-flex rounded-full bg-white px-4 py-2 text-sm font-medium text-slate-950" to="/login">Return to sign in</Link></div>

  return <div className="space-y-4 rounded-3xl border border-slate-800 bg-slate-900/70 p-6">
    <div><h1 className="text-2xl font-semibold text-white">Submission Review</h1><p className="mt-1 text-sm text-slate-400">Review candidate submissions and move them through the hiring pipeline.</p></div>
    <div className="grid gap-3 md:grid-cols-3">
      <select className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" value={status} onChange={(event) => setStatus(event.target.value as SubmissionStatus | '')}><option value="">All statuses</option>{submissionStatuses.map((value) => <option key={value} value={value}>{value}</option>)}</select>
      <input className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" placeholder="Job ID" inputMode="numeric" value={jobId} onChange={(event) => setJobId(event.target.value.replace(/\D/g, ''))} />
      <input className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" placeholder="Candidate ID" inputMode="numeric" value={candidateId} onChange={(event) => setCandidateId(event.target.value.replace(/\D/g, ''))} />
    </div>
    {error && <p className="text-sm text-rose-300">{error}</p>}
    {loading ? <p className="py-8 text-sm text-slate-400">Loading submissions...</p> : submissions.length === 0 ? <p className="py-8 text-sm text-slate-400">No submissions match these filters.</p> : <div className="overflow-x-auto"><table className="min-w-full text-left text-sm text-slate-300"><thead><tr className="border-b border-slate-800 text-slate-400"><th className="px-3 py-2">Candidate</th><th className="px-3 py-2">Job</th><th className="px-3 py-2">Company</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Notes</th><th className="px-3 py-2">Dates</th></tr></thead><tbody>{submissions.map((submission) => <tr className="border-b border-slate-800/70 align-top" key={submission.id}><td className="px-3 py-3 text-white">{submission.candidate.first_name} {submission.candidate.last_name}<div className="text-xs text-slate-500">{submission.candidate.email}</div></td><td className="px-3 py-3 text-white">{submission.job.title}<div className="text-xs text-slate-500">{submission.job.location || 'Location not specified'}</div></td><td className="px-3 py-3">{submission.company.name}</td><td className="px-3 py-3"><select className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-white" value={submission.status} disabled={nextStatuses[submission.status].length === 0} onChange={(event) => void changeSubmission(submission, event.target.value as SubmissionStatus)}><option value={submission.status}>{submission.status}</option>{nextStatuses[submission.status].map((value) => <option key={value} value={value}>{value}</option>)}</select></td><td className="min-w-56 px-3 py-3"><textarea className="w-full rounded-md border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-white" rows={2} value={notes[submission.id] || ''} onChange={(event) => setNotes((current) => ({ ...current, [submission.id]: event.target.value }))} /><button className="mt-1 text-xs text-sky-300 hover:text-sky-200" type="button" onClick={() => void saveNotes(submission)}>Save notes</button></td><td className="whitespace-nowrap px-3 py-3 text-xs text-slate-400">Created {formatDate(submission.created_at)}<br />Updated {formatDate(submission.updated_at)}</td></tr>)}</tbody></table></div>}
  </div>
}