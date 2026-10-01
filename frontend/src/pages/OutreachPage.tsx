import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, Mail, RefreshCw } from 'lucide-react'
import {
  cancelOutreach,
  createOutreachDraft,
  fetchCandidateHotlist,
  fetchJobs,
  fetchOutreach,
  fetchVendorIntelligence,
  markOutreachSent,
  previewOutreachDraft,
  searchVendorIntelligence,
  updateOutreach,
  type CandidateHotlistItem,
  type Job,
  type OutreachEntities,
  type OutreachPreview,
  type OutreachRecord,
  type OutreachTemplateType,
  type VendorIntelligenceItem,
  type IntelligenceContact,
} from '../lib/api'

const HISTORY_PAGE_SIZE = 10

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : 'Not sent'
}

export default function OutreachPage() {
  const [candidateQuery, setCandidateQuery] = useState('')
  const [jobQuery, setJobQuery] = useState('')
  const [vendorQuery, setVendorQuery] = useState('')
  const [candidates, setCandidates] = useState<CandidateHotlistItem[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [vendors, setVendors] = useState<VendorIntelligenceItem[]>([])
  const [contacts, setContacts] = useState<IntelligenceContact[]>([])
  const [selection, setSelection] = useState({ candidate_id: '', job_id: '', vendor_id: '', contact_id: '' })
  const [template, setTemplate] = useState<OutreachTemplateType>('candidate_submission')
  const [preview, setPreview] = useState<OutreachPreview | null>(null)
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [history, setHistory] = useState<OutreachRecord[]>([])
  const [historyPage, setHistoryPage] = useState(1)
  const [historyTotal, setHistoryTotal] = useState(0)
  const [refreshHistory, setRefreshHistory] = useState(0)
  const [loadingOptions, setLoadingOptions] = useState(true)
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    let active = true
    const timer = window.setTimeout(() => {
      setLoadingOptions(true)
      Promise.all([
        fetchCandidateHotlist({ q: candidateQuery.trim() || undefined, page_size: 100 }),
        fetchJobs({ title: jobQuery.trim() || undefined, page: 1, page_size: 100 }),
        searchVendorIntelligence(vendorQuery.trim(), 1, 100),
      ])
        .then(([candidatePage, jobResults, vendorPage]) => {
          if (!active) return
          setCandidates(candidatePage.items)
          setJobs(jobResults)
          setVendors(vendorPage.items)
          setError('')
        })
        .catch(() => { if (active) setError('Outreach options are unavailable for this account.') })
        .finally(() => { if (active) setLoadingOptions(false) })
    }, 180)
    return () => { active = false; window.clearTimeout(timer) }
  }, [candidateQuery, jobQuery, vendorQuery])

  useEffect(() => {
    let active = true
    if (!selection.vendor_id) {
      setContacts([])
      setSelection((current) => current.contact_id ? { ...current, contact_id: '' } : current)
      return () => { active = false }
    }
    fetchVendorIntelligence(Number(selection.vendor_id))
      .then((profile) => { if (active) setContacts(profile.contacts) })
      .catch(() => { if (active) { setContacts([]); setError('Contacts could not be loaded for this vendor.') } })
    return () => { active = false }
  }, [selection.vendor_id])

  useEffect(() => {
    let active = true
    setLoadingHistory(true)
    fetchOutreach({ page: historyPage, page_size: HISTORY_PAGE_SIZE })
      .then((result) => {
        if (!active) return
        setHistory(result.items)
        setHistoryTotal(result.total)
      })
      .catch(() => { if (active) setError('Outreach history could not be loaded.') })
      .finally(() => { if (active) setLoadingHistory(false) })
    return () => { active = false }
  }, [historyPage, refreshHistory])

  function entityIds(): OutreachEntities {
    return {
      candidate_id: selection.candidate_id ? Number(selection.candidate_id) : undefined,
      job_id: selection.job_id ? Number(selection.job_id) : undefined,
      vendor_id: selection.vendor_id ? Number(selection.vendor_id) : undefined,
      contact_id: selection.contact_id ? Number(selection.contact_id) : undefined,
    }
  }

  async function generatePreview() {
    setWorking(true)
    setError('')
    setNotice('')
    setEditingId(null)
    try {
      const result = await previewOutreachDraft({ ...entityIds(), template_type: template })
      setPreview(result)
      setSubject(result.subject)
      setBody(result.body)
    } catch {
      setError('Draft preview could not be generated. Check the selected relationships and your access.')
      setPreview(null)
    } finally {
      setWorking(false)
    }
  }

  async function saveDraft() {
    setWorking(true)
    setError('')
    setNotice('')
    try {
      if (editingId !== null) {
        await updateOutreach(editingId, { subject, body })
        setNotice('Draft changes saved.')
      } else {
        await createOutreachDraft({ ...entityIds(), subject, body })
        setNotice('Draft saved. No email was sent.')
      }
      setEditingId(null)
      setRefreshHistory((value) => value + 1)
    } catch (saveError) {
      setError(saveError instanceof Error && saveError.message.includes('409')
        ? 'An active draft already exists for this relationship.'
        : 'The draft could not be saved.')
    } finally {
      setWorking(false)
    }
  }

  async function runHistoryAction(action: (id: number) => Promise<OutreachRecord>, item: OutreachRecord, message: string) {
    setWorking(true)
    setError('')
    setNotice('')
    try {
      await action(item.id)
      setNotice(message)
      setRefreshHistory((value) => value + 1)
    } catch {
      setError('The outreach status could not be updated.')
    } finally {
      setWorking(false)
    }
  }

  function editDraft(item: OutreachRecord) {
    setEditingId(item.id)
    setPreview(null)
    setSubject(item.subject)
    setBody(item.body)
    setNotice('Editing saved draft. Save changes when ready.')
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <p className="text-sm font-medium text-cyan-400">Recruiting</p>
          <h1 className="mt-1 text-2xl font-semibold text-white">Outreach workspace</h1>
          <p className="mt-1 text-sm text-slate-400">Create, review, and track drafts. Messages are never sent from this system.</p>
        </div>
        <Mail size={20} className="text-cyan-400" aria-hidden="true" />
      </header>

      {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}
      {notice && <p role="status" className="text-sm text-emerald-300">{notice}</p>}

      <section className="grid gap-6 xl:grid-cols-[minmax(280px,0.8fr)_minmax(0,1.2fr)]">
        <div className="space-y-4 border-b border-slate-800 pb-5 xl:border-b-0 xl:border-r xl:pr-6">
          <h2 className="font-medium text-white">New draft</h2>
          <label className="block text-xs text-slate-400">Template
            <select value={template} onChange={(event) => setTemplate(event.target.value as OutreachTemplateType)} className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white">
              <option value="candidate_submission">Candidate submission</option>
              <option value="vendor_relationship">Vendor relationship</option>
              <option value="follow_up">Follow-up</option>
            </select>
          </label>
          <label className="block text-xs text-slate-400">Find candidate
            <input value={candidateQuery} onChange={(event) => setCandidateQuery(event.target.value)} placeholder="Search name or email" className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white" />
            <select aria-label="Candidate" value={selection.candidate_id} onChange={(event) => setSelection({ ...selection, candidate_id: event.target.value })} className="mt-2 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white">
              <option value="">No candidate selected</option>
              {candidates.map(({ candidate }) => <option key={candidate.id} value={candidate.id}>{candidate.first_name} {candidate.last_name}</option>)}
            </select>
          </label>
          <label className="block text-xs text-slate-400">Find job
            <input value={jobQuery} onChange={(event) => setJobQuery(event.target.value)} placeholder="Search job title" className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white" />
            <select aria-label="Job" value={selection.job_id} onChange={(event) => setSelection({ ...selection, job_id: event.target.value })} className="mt-2 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white">
              <option value="">No job selected</option>
              {jobs.map((job) => <option key={job.id} value={job.id}>{job.title}{job.location ? ` · ${job.location}` : ''}</option>)}
            </select>
          </label>
          <label className="block text-xs text-slate-400">Find vendor
            <input value={vendorQuery} onChange={(event) => setVendorQuery(event.target.value)} placeholder="Search vendor" className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white" />
            <select aria-label="Vendor" value={selection.vendor_id} onChange={(event) => setSelection({ ...selection, vendor_id: event.target.value, contact_id: '' })} className="mt-2 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white">
              <option value="">No vendor selected</option>
              {vendors.map((vendor) => <option key={vendor.id} value={vendor.id}>{vendor.name}{vendor.company_name ? ` · ${vendor.company_name}` : ''}</option>)}
            </select>
          </label>
          <label className="block text-xs text-slate-400">Contact
            <select aria-label="Contact" value={selection.contact_id} onChange={(event) => setSelection({ ...selection, contact_id: event.target.value })} disabled={!selection.vendor_id} className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
              <option value="">No contact selected</option>
              {contacts.map((contact) => <option key={contact.id} value={contact.id}>{contact.full_name} · {contact.email}</option>)}
            </select>
          </label>
          <button type="button" disabled={working || loadingOptions} onClick={() => void generatePreview()} className="w-full rounded-md bg-cyan-700 px-3 py-2 text-sm font-medium text-white hover:bg-cyan-600 disabled:opacity-50">{working ? 'Working…' : 'Generate draft'}</button>
          {loadingOptions && <p className="text-xs text-slate-500">Loading authorized options…</p>}
        </div>

        <section aria-label="Draft editor" className="min-w-0 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-medium text-white">{editingId ? 'Edit saved draft' : 'Review draft'}</h2>
            {preview?.recipient_email && <span className="break-all text-xs text-slate-400">To: {preview.recipient_email}</span>}
          </div>
          {preview && <div className="border-l-2 border-cyan-800 pl-3">
            <h3 className="text-xs font-medium uppercase text-slate-400">Personalization evidence</h3>
            <ul className="mt-2 space-y-1 text-sm text-slate-300">{preview.evidence.map((fact) => <li key={fact}>{fact}</li>)}</ul>
          </div>}
          <label className="block text-xs text-slate-400">Subject
            <input value={subject} onChange={(event) => setSubject(event.target.value)} disabled={!preview && editingId === null} className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50" />
          </label>
          <label className="block text-xs text-slate-400">Body
            <textarea value={body} onChange={(event) => setBody(event.target.value)} disabled={!preview && editingId === null} rows={12} className="mt-1 w-full resize-y rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm leading-6 text-white disabled:opacity-50" />
          </label>
          <button type="button" disabled={working || (!preview && editingId === null) || !subject.trim() || !body.trim()} onClick={() => void saveDraft()} className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50">{editingId ? 'Save changes' : 'Save draft'}</button>
          <p className="text-xs text-slate-500">Saving stores a draft only. Send it yourself, then mark it sent here.</p>
        </section>
      </section>

      <section className="border-t border-slate-800 pt-5">
        <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div><h2 className="font-medium text-white">Outreach history</h2><p className="mt-1 text-xs text-slate-500">{historyTotal} records visible to your account</p></div>
          <button type="button" onClick={() => setRefreshHistory((value) => value + 1)} aria-label="Refresh outreach history" title="Refresh history" className="rounded p-2 text-slate-300 hover:bg-slate-800"><RefreshCw size={16} /></button>
        </header>
        {loadingHistory ? <p className="py-4 text-sm text-slate-400">Loading history…</p> : history.length === 0 ? (
          <p className="border-y border-slate-800 py-4 text-sm text-slate-400">No outreach drafts yet.</p>
        ) : <ul className="divide-y divide-slate-800 border-y border-slate-800">{history.map((item) => (
          <li key={item.id} className="flex flex-col gap-3 py-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <p className="truncate font-medium text-slate-100">{item.subject}</p>
              <p className="mt-1 text-xs text-slate-400">{[item.candidate_name, item.job_title, item.vendor_name, item.contact_name].filter(Boolean).join(' · ') || 'General outreach'}</p>
              <p className="mt-1 text-xs text-slate-500">Created {formatDate(item.created_at)}{item.sent_at ? ` · Sent ${formatDate(item.sent_at)}` : ''}</p>
            </div>
            <div className="flex shrink-0 flex-wrap items-center gap-2">
              <span className={`text-xs font-medium ${item.status === 'SENT' ? 'text-emerald-300' : item.status === 'CANCELLED' ? 'text-slate-500' : 'text-cyan-300'}`}>{item.status}</span>
              {(item.status === 'DRAFT' || item.status === 'READY') && <>
                <button type="button" onClick={() => editDraft(item)} className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-200 hover:border-slate-500">Edit</button>
                {item.status === 'DRAFT' && <button type="button" disabled={working} onClick={() => void updateOutreach(item.id, { status: 'READY' }).then(() => setRefreshHistory((value) => value + 1)).catch(() => setError('Could not mark draft ready.'))} className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-200 hover:border-slate-500 disabled:opacity-50">Ready</button>}
                <button type="button" disabled={working} onClick={() => void runHistoryAction(markOutreachSent, item, 'Marked sent manually.')} className="rounded bg-emerald-800 px-2 py-1 text-xs text-white hover:bg-emerald-700 disabled:opacity-50">Mark sent</button>
                <button type="button" disabled={working} onClick={() => void runHistoryAction(cancelOutreach, item, 'Outreach cancelled.')} className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:border-slate-500 disabled:opacity-50">Cancel</button>
              </>}
            </div>
          </li>
        ))}</ul>}
        <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
          <span>Page {historyPage} of {Math.max(1, Math.ceil(historyTotal / HISTORY_PAGE_SIZE))}</span>
          <div className="flex gap-1">
            <button type="button" disabled={historyPage <= 1} onClick={() => setHistoryPage((value) => value - 1)} aria-label="Previous outreach page" className="rounded p-2 text-slate-300 hover:bg-slate-800 disabled:opacity-30"><ChevronLeft size={17} /></button>
            <button type="button" disabled={historyPage * HISTORY_PAGE_SIZE >= historyTotal} onClick={() => setHistoryPage((value) => value + 1)} aria-label="Next outreach page" className="rounded p-2 text-slate-300 hover:bg-slate-800 disabled:opacity-30"><ChevronRight size={17} /></button>
          </div>
        </div>
      </section>
    </div>
  )
}