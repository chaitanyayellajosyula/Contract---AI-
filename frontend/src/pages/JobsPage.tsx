import { useEffect, useState } from 'react'
import { fetchJobs } from '../lib/api'

export default function JobsPage() {
  const [jobs, setJobs] = useState<any[]>([])

  useEffect(() => {
    async function loadJobs() {
      try {
        const data = await fetchJobs()
        setJobs(data || [])
      } catch {
        setJobs([])
      }
    }

    void loadJobs()
  }, [])

  return (
    <div className="space-y-4 rounded-3xl border border-slate-800 bg-slate-900/70 p-6">
      <h1 className="text-2xl font-semibold text-white">Jobs</h1>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm text-slate-300">
          <thead>
            <tr className="border-b border-slate-800 text-left text-slate-400">
              <th className="px-3 py-2">Title</th>
              <th className="px-3 py-2">Company</th>
              <th className="px-3 py-2">Location</th>
              <th className="px-3 py-2">Employment Type</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Source</th>
              <th className="px-3 py-2">Posted</th>
            </tr>
          </thead>
          <tbody>
            {jobs.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-3 py-4 text-slate-400">No jobs found.</td>
              </tr>
            ) : (
              jobs.map((job) => (
                <tr key={job.id} className="border-b border-slate-800/70">
                  <td className="px-3 py-2 text-white">
                    {job.source_url ? (
                      <a href={job.source_url} target="_blank" rel="noreferrer" className="text-sky-400 hover:text-sky-300 underline">
                        {job.title || '—'}
                      </a>
                    ) : (
                      job.title || '—'
                    )}
                  </td>
                  <td className="px-3 py-2">{job.company || '—'}</td>
                  <td className="px-3 py-2">{job.location || '—'}</td>
                  <td className="px-3 py-2">{job.employment_type || '—'}</td>
                  <td className="px-3 py-2">{job.status || '—'}</td>
                  <td className="px-3 py-2">{job.source || '—'}</td>
                  <td className="px-3 py-2">{job.posted_at ? new Date(job.posted_at).toLocaleDateString() : '—'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
