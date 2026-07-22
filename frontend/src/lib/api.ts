const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`)
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
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
