import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '../lib/api'

export default function LoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('admin@example.com')
  const [password, setPassword] = useState('password')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      await login(email, password)
      navigate('/submissions')
    } catch {
      setError('Unable to sign in with those credentials.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4 text-slate-100">
      <div className="w-full max-w-md rounded-3xl border border-slate-800 bg-slate-900/80 p-8 shadow-2xl">
        <p className="text-sm uppercase tracking-[0.3em] text-slate-400">Contract Hunter AI</p>
        <h1 className="mt-4 text-3xl font-semibold">Welcome back</h1>
        <p className="mt-2 text-sm text-slate-400">Sign in to open the application foundation.</p>
        <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
          <label className="block text-sm text-slate-300">Email<input className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
          <label className="block text-sm text-slate-300">Password<input className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
          {error && <p className="text-sm text-rose-300">{error}</p>}
          <button className="w-full rounded-full bg-white px-4 py-3 text-sm font-medium text-slate-950 transition hover:bg-slate-200 disabled:opacity-60" type="submit" disabled={submitting}>{submitting ? 'Signing in...' : 'Sign in'}</button>
        </form>
      </div>
    </div>
  )
}
