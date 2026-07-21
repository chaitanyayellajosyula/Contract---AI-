import React from 'react'
import ReactDOM from 'react-dom/client'
import './styles.css'

function App() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center">
      <div className="text-center space-y-4">
        <p className="text-sm uppercase tracking-[0.3em] text-slate-400">Contract Hunter AI</p>
        <h1 className="text-4xl font-semibold">Project foundation initialized</h1>
        <p className="text-slate-400">Frontend shell is ready for future feature development.</p>
      </div>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
