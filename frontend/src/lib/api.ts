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

export async function fetchJobs() {
  return request<any[]>('/jobs')
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
