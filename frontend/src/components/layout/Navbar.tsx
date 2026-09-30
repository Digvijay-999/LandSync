import React from 'react'
import { Layers, Activity, Database, Server, RefreshCw, Sparkles } from 'lucide-react'
import { useHealth } from '../../hooks/useHealth'
import { StatusBadge } from '../common/StatusBadge'
import { useAppStore } from '../../stores/useAppStore'

export const Navbar: React.FC = () => {
  const { data: health, isLoading, isError, refetch } = useHealth()
  const { assistantOpen, toggleAssistant } = useAppStore()

  return (
    <header className="h-14 border-b border-border bg-surface-900/95 backdrop-blur px-4 flex items-center justify-between sticky top-0 z-30">
      {/* Brand */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded bg-cyan-950/80 border border-cyan-800 flex items-center justify-center text-cyan-400">
            <Layers className="w-4 h-4" />
          </div>
          <div>
            <span className="font-bold text-slate-100 tracking-wider text-sm font-mono">LANDSYNC</span>
            <span className="text-cyan-400 font-mono text-xs font-semibold ml-1.5 px-1.5 py-0.5 rounded bg-cyan-950/60 border border-cyan-900/80">AI</span>
          </div>
        </div>
        <span className="hidden sm:inline-block text-xs font-mono text-slate-400 border-l border-border pl-3">
          Geospatial Harmonization Platform
        </span>
      </div>

      {/* Diagnostics / Status Bar */}
      <div className="flex items-center gap-3">
        {/* Backend Status */}
        <div className="flex items-center gap-2 text-xs font-mono text-slate-300 bg-surface-950 px-2.5 py-1 rounded border border-border">
          <Server className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-slate-400 hidden md:inline">API:</span>
          {isLoading ? (
            <span className="text-slate-400 animate-pulse">Checking...</span>
          ) : isError ? (
            <StatusBadge status="down" />
          ) : (
            <StatusBadge status={health?.status || 'healthy'} />
          )}
        </div>

        {/* PostGIS Status */}
        <div className="flex items-center gap-2 text-xs font-mono text-slate-300 bg-surface-950 px-2.5 py-1 rounded border border-border">
          <Database className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-slate-400 hidden md:inline">PostGIS:</span>
          {isLoading ? (
            <span className="text-slate-400 animate-pulse">...</span>
          ) : health?.database?.postgis_installed ? (
            <span className="text-emerald-400 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              <span>Active</span>
            </span>
          ) : health?.database?.connected ? (
            <span className="text-amber-400">PG Only</span>
          ) : (
            <span className="text-rose-400">Offline</span>
          )}
        </div>

        <button
          onClick={() => refetch()}
          title="Refresh health diagnostic"
          className="p-1.5 rounded text-slate-400 hover:text-slate-200 hover:bg-surface-800 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>

        {/* AI Assistant Toggle Button */}
        <button
          onClick={toggleAssistant}
          className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-mono transition-all ${
            assistantOpen
              ? 'bg-cyan-600 text-white shadow-sm shadow-cyan-500/30 border border-cyan-400'
              : 'bg-cyan-950/80 text-cyan-300 hover:bg-cyan-900 border border-cyan-800 hover:border-cyan-600'
          }`}
          title="Toggle LandSync AI Geospatial Assistant"
        >
          <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
          <span className="font-semibold">Ask AI</span>
        </button>
      </div>
    </header>
  )
}
