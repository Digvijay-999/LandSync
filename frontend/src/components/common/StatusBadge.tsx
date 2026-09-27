import React from 'react'
import { cn } from '../../lib/utils'

interface StatusBadgeProps {
  status: string
  className?: string
  dot?: boolean
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className, dot = true }) => {
  const normalized = status.toLowerCase()

  let colorClasses = 'bg-slate-800 text-slate-300 border-slate-700'
  let dotColor = 'bg-slate-400'

  if (normalized === 'healthy' || normalized === 'connected' || normalized === 'active' || normalized === 'completed') {
    colorClasses = 'bg-emerald-950/40 text-emerald-300 border-emerald-800/60'
    dotColor = 'bg-emerald-400'
  } else if (normalized === 'degraded' || normalized === 'processing' || normalized === 'pending') {
    colorClasses = 'bg-amber-950/40 text-amber-300 border-amber-800/60'
    dotColor = 'bg-amber-400 animate-pulse'
  } else if (normalized === 'error' || normalized === 'down' || normalized === 'failed' || normalized === 'disconnected') {
    colorClasses = 'bg-rose-950/40 text-rose-300 border-rose-800/60'
    dotColor = 'bg-rose-500'
  }

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-medium border uppercase tracking-wider',
        colorClasses,
        className
      )}
    >
      {dot && <span className={cn('w-1.5 h-1.5 rounded-full', dotColor)} />}
      {status}
    </span>
  )
}
