const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const TOKEN_KEY = 'contract-hunter-access-token'

export const submissionStatuses = ['SUBMITTED', 'REVIEWING', 'INTERVIEW', 'REJECTED', 'PLACED'] as const
export type SubmissionStatus = (typeof submissionStatuses)[number]

export type Submission = {
  id: number
  candidate_id: number
  job_id: number
  company_id: number
  submitted_by_user_id: number
  status: SubmissionStatus
  notes: string | null
  created_at: string
  updated_at: string
  candidate: { id: number; first_name: string; last_name: string; email: string }
  job: { id: number; title: string; location: string | null }
  company: { id: number; name: string }
}

export type Job = {
  id: number
  title: string
  description: string | null
  location: string | null
  employment_type: string | null
  remote_type: string | null
  status: string | null
  source: string | null
  source_job_id: string | null
  source_url: string | null
  apply_url: string | null
  source_company: string | null
  source_updated_at: string | null
  source_metadata: Record<string, unknown> | null
  posted_at: string | null
  created_at: string
  updated_at: string
  viewed: boolean
  saved: boolean
  hidden: boolean
  bookmarked: boolean
  company: string | null
}

export type JobFilters = {
  title?: string
  engagement?: string
  remote_type?: string
  location?: string
  source?: string
  company?: string
  freshness?: string
  viewed?: boolean
  saved?: boolean
  hidden?: boolean
  page?: number
  page_size?: number
}

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function clearAccessToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export class ApiError extends Error {
  status: number

  constructor(status: number) {
    super(`Request failed: ${status}`)
    this.status = status
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const token = getAccessToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })
  if (!response.ok) {
    if (response.status === 401) clearAccessToken()
    throw new ApiError(response.status)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export async function login(email: string, password: string) {
  const response = await request<{ access_token: string }>('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  localStorage.setItem(TOKEN_KEY, response.access_token)
}

export async function fetchCompanies() {
  return request<any[]>('/companies')
}

export async function fetchVendors() {
  return request<any[]>('/vendors')
}

export async function fetchVendorContacts() {
  return request<any[]>('/vendor-contacts')
}

export async function fetchJobs(filters: JobFilters = {}) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value))
  })
  const query = params.toString()
  return request<Job[]>(`/jobs${query ? `?${query}` : ''}`)
}

export async function updateJobStatus(id: number, updates: { viewed?: boolean; saved?: boolean; hidden?: boolean }) {
  return request<Job>(`/jobs/${id}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  })
}

export async function fetchSubmissions(filters: { status?: SubmissionStatus; jobId?: number; candidateId?: number } = {}) {
  const params = new URLSearchParams()
  if (filters.status) params.set('status', filters.status)
  if (filters.jobId) params.set('job_id', String(filters.jobId))
  if (filters.candidateId) params.set('candidate_id', String(filters.candidateId))
  const query = params.toString()
  return request<Submission[]>(`/submissions${query ? `?${query}` : ''}`)
}

export async function updateSubmission(id: number, updates: { status?: SubmissionStatus; notes?: string }) {
  return request<Submission>(`/submissions/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  })
}
