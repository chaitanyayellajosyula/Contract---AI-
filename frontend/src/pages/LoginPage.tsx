import { Link } from 'react-router-dom'

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4 text-slate-100">
      <div className="w-full max-w-md rounded-3xl border border-slate-800 bg-slate-900/80 p-8 shadow-2xl">
        <p className="text-sm uppercase tracking-[0.3em] text-slate-400">Contract Hunter AI</p>
        <h1 className="mt-4 text-3xl font-semibold">Welcome back</h1>
        <p className="mt-2 text-sm text-slate-400">Sign in to open the application foundation.</p>
        <div className="mt-8 space-y-3">
          <div className="rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3 text-sm text-slate-300">Username: admin</div>
          <div className="rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3 text-sm text-slate-300">Password: password</div>
          <Link to="/" className="flex justify-center rounded-full bg-white px-4 py-3 text-sm font-medium text-slate-950 transition hover:bg-slate-200">
            Continue to dashboard
          </Link>
        </div>
      </div>
    </div>
  )
}
