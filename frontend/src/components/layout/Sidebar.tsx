import React from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  FolderGit2,
  Database,
  GitMerge,
  ShieldCheck,
  FileDown,
  Terminal,
} from 'lucide-react'
import { cn } from '../../lib/utils'

export const Sidebar: React.FC = () => {
  const activeNavClass = ({ isActive }: { isActive: boolean }) =>
    cn(
      'flex items-center gap-3 px-3 py-2 rounded text-xs font-mono transition-colors',
      isActive
        ? 'bg-cyan-950/50 text-cyan-300 border border-cyan-800/80 font-medium'
        : 'text-slate-400 hover:text-slate-200 hover:bg-surface-800/60'
    )

  return (
    <aside className="w-56 border-r border-border bg-surface-900/60 flex flex-col justify-between p-3 select-none">
      <div className="space-y-6">
        <div>
          <div className="px-3 mb-2 text-[10px] font-mono uppercase tracking-wider text-slate-400">
            Platform Core
          </div>
          <nav className="space-y-1">
            <NavLink to="/dashboard" className={activeNavClass}>
              <LayoutDashboard className="w-4 h-4" />
              <span>Dashboard</span>
            </NavLink>

            <NavLink to="/projects" className={activeNavClass}>
              <FolderGit2 className="w-4 h-4" />
              <span>Projects</span>
            </NavLink>
          </nav>
        </div>

        <div>
          <div className="px-3 mb-2 text-[10px] font-mono uppercase tracking-wider text-slate-400">
            Pipeline Modules (Roadmap)
          </div>
          <nav className="space-y-1">
            <div
              className="flex items-center justify-between px-3 py-2 rounded text-xs font-mono text-slate-400 cursor-not-allowed"
              title="Introduced in Ingestion Milestone"
            >
              <span className="flex items-center gap-3">
                <Database className="w-4 h-4" />
                <span>Datasets</span>
              </span>
              <span className="text-[10px] text-slate-400">v0.2</span>
            </div>

            <div
              className="flex items-center justify-between px-3 py-2 rounded text-xs font-mono text-slate-400 cursor-not-allowed"
              title="Introduced in Harmonization Milestone"
            >
              <span className="flex items-center gap-3">
                <GitMerge className="w-4 h-4" />
                <span>Harmonization</span>
              </span>
              <span className="text-[10px] text-slate-400">v0.3</span>
            </div>

            <div
              className="flex items-center justify-between px-3 py-2 rounded text-xs font-mono text-slate-400 cursor-not-allowed"
              title="Introduced in Review Milestone"
            >
              <span className="flex items-center gap-3">
                <ShieldCheck className="w-4 h-4" />
                <span>Validation</span>
              </span>
              <span className="text-[10px] text-slate-400">v0.4</span>
            </div>

            <div
              className="flex items-center justify-between px-3 py-2 rounded text-xs font-mono text-slate-400 cursor-not-allowed"
              title="Introduced in Export Milestone"
            >
              <span className="flex items-center gap-3">
                <FileDown className="w-4 h-4" />
                <span>Export</span>
              </span>
              <span className="text-[10px] text-slate-400">v0.5</span>
            </div>
          </nav>
        </div>
      </div>

      {/* System status footer */}
      <div className="pt-3 border-t border-border/80">
        <div className="flex items-center gap-2 px-2 py-1.5 rounded bg-surface-950/70 border border-border text-[11px] font-mono text-slate-400">
          <Terminal className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
          <span className="truncate">Milestone: 01-FOUNDATION</span>
        </div>
      </div>
    </aside>
  )
}
