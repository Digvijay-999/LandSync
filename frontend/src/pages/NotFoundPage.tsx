import React from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Compass } from 'lucide-react'

export const NotFoundPage: React.FC = () => {
  return (
    <div className="py-24 text-center max-w-md mx-auto space-y-4">
      <Compass className="w-12 h-12 text-slate-400 mx-auto" />
      <h1 className="text-xl font-mono font-bold text-slate-200">404 — ROUTE NOT FOUND</h1>
      <p className="text-xs text-slate-400">
        The requested spatial coordinates or view do not exist.
      </p>
      <Link
        to="/dashboard"
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-surface-900 border border-border text-xs font-mono text-cyan-400 hover:text-cyan-300"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>Return to Dashboard</span>
      </Link>
    </div>
  )
}
