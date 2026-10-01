import React from 'react'
import { Link } from 'react-router-dom'
import { Server, Database, Globe, FolderGit2, ArrowUpRight, Cpu, Compass } from 'lucide-react'
import { useHealth } from '../hooks/useHealth'
import { useProjects } from '../hooks/useProjects'
import { StatusBadge } from '../components/common/StatusBadge'
import { PipelineIndicator } from '../components/common/PipelineIndicator'
import { formatDate } from '../lib/utils'

export const DashboardPage: React.FC = () => {
  const { data: health, isLoading: healthLoading } = useHealth()
  const { data: projectsData, isLoading: projectsLoading } = useProjects(0, 5)

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/80 pb-4">
        <div>
          <h1 className="text-xl font-bold font-mono text-slate-100 flex items-center gap-2">
            <span>SYSTEM DASHBOARD</span>
            <span className="text-xs px-2 py-0.5 rounded bg-surface-900 border border-border text-slate-400 font-normal">
              LANDSYNC-NODE-01
            </span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time status of backend services, PostGIS spatial engine, and harmonization workspaces.
          </p>
        </div>

        <Link
          to="/projects"
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded bg-cyan-950/70 border border-cyan-800 text-cyan-300 text-xs font-mono font-medium hover:bg-cyan-900/60 transition-colors self-start sm:self-auto"
        >
          <FolderGit2 className="w-3.5 h-3.5" />
          <span>View All Projects</span>
          <ArrowUpRight className="w-3.5 h-3.5" />
        </Link>
      </div>

      {/* Diagnostic & Telemetry Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* API Backend Card */}
        <div className="bg-surface-900 border border-border rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
              <Server className="w-4 h-4 text-cyan-400" />
              <span>FastAPI Backend</span>
            </div>
            <StatusBadge status={healthLoading ? 'checking' : health?.status || 'healthy'} />
          </div>
          <div className="space-y-1">
            <div className="text-lg font-mono font-semibold text-slate-200">
              v{health?.version || '0.1.0'}
            </div>
            <div className="text-[11px] font-mono text-slate-400 truncate">
              Env: <span className="text-slate-300">{health?.environment || 'development'}</span>
            </div>
          </div>
        </div>

        {/* PostgreSQL + PostGIS Card */}
        <div className="bg-surface-900 border border-border rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
              <Database className="w-4 h-4 text-emerald-400" />
              <span>PostgreSQL & PostGIS</span>
            </div>
            <StatusBadge
              status={
                healthLoading
                  ? 'checking'
                  : health?.database?.connected
                  ? 'connected'
                  : 'error'
              }
            />
          </div>
          <div className="space-y-1">
            <div className="text-lg font-mono font-semibold text-slate-200">
              {health?.database?.postgis_installed ? 'PostGIS Active' : 'Connected'}
            </div>
            <div className="text-[11px] font-mono text-slate-400 truncate" title={health?.database?.postgis_version || 'Ready'}>
              {health?.database?.postgis_version ? (
                <span className="text-emerald-400/90">{health.database.postgis_version}</span>
              ) : (
                <span>PostGIS Spatial Engine ready</span>
              )}
            </div>
          </div>
        </div>

        {/* Spatial CRS Engine */}
        <div className="bg-surface-900 border border-border rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
              <Globe className="w-4 h-4 text-cyan-400" />
              <span>Default Spatial CRS</span>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-surface-950 border border-border text-slate-300">
              WGS 84
            </span>
          </div>
          <div className="space-y-1">
            <div className="text-lg font-mono font-semibold text-slate-200">
              EPSG:4326
            </div>
            <div className="text-[11px] font-mono text-slate-400">
              Standard Geographic Coordinate System
            </div>
          </div>
        </div>

        {/* Workspaces Metric */}
        <div className="bg-surface-900 border border-border rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
              <Cpu className="w-4 h-4 text-purple-400" />
              <span>Active Workspaces</span>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-950/40 text-purple-300 border border-purple-800">
              DB Synced
            </span>
          </div>
          <div className="space-y-1">
            <div className="text-lg font-mono font-semibold text-slate-200">
              {projectsLoading ? '...' : projectsData?.total || 0}
            </div>
            <div className="text-[11px] font-mono text-slate-400">
              Harmonization project instances
            </div>
          </div>
        </div>
      </div>

      {/* M9 Geospatial Intelligence Engine Banner */}
      <div className="bg-surface-900 border border-border rounded-lg p-5">
        <div className="flex items-center justify-between border-b border-border/80 pb-3 mb-4">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded bg-purple-950/60 border border-purple-800/80 text-purple-400">
              <Compass className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold font-mono uppercase text-slate-200">
                PostGIS Geospatial Intelligence Engine (M9)
              </h2>
              <p className="text-xs text-slate-400">
                Controlled read-only spatial tools and AI-driven topological queries.
              </p>
            </div>
          </div>
          <span className="text-[11px] font-mono px-2.5 py-1 rounded bg-purple-950/40 border border-purple-800 text-purple-300">
            Real PostGIS 3.4+ Execution
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs font-mono">
          <div className="p-3 rounded bg-surface-950 border border-border/70">
            <span className="text-cyan-400 font-semibold block mb-1">ST_DWithin & Buffer</span>
            <p className="text-[11px] text-slate-400 font-sans">
              Proximity queries and analytical buffer overlays around parcels & municipal assets.
            </p>
          </div>
          <div className="p-3 rounded bg-surface-950 border border-border/70">
            <span className="text-amber-400 font-semibold block mb-1">ST_Intersects & Area</span>
            <p className="text-[11px] text-slate-400 font-sans">
              Topological intersections, polygon overlap percentages, and boundary alignments.
            </p>
          </div>
          <div className="p-3 rounded bg-surface-950 border border-border/70">
            <span className="text-rose-400 font-semibold block mb-1">Spatial Conflict Clusters</span>
            <p className="text-[11px] text-slate-400 font-sans">
              Geographic aggregation of unresolved multi-source attribute conflicts.
            </p>
          </div>
          <div className="p-3 rounded bg-surface-950 border border-border/70">
            <span className="text-emerald-400 font-semibold block mb-1">Dataset Comparison</span>
            <p className="text-[11px] text-slate-400 font-sans">
              Dual-source coverage audits, intersecting pairs, and unmatched boundary detection.
            </p>
          </div>
        </div>
      </div>

      {/* Harmonization Pipeline Architecture Section */}
      <PipelineIndicator />

      {/* Recent Workspaces Table */}
      <div className="bg-surface-900 border border-border rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold font-mono uppercase text-slate-200">
              Recent Harmonization Projects
            </h2>
            <p className="text-xs text-slate-400">
              Workspaces configured for multi-dataset ingest and spatial normalization.
            </p>
          </div>
          <Link
            to="/projects"
            className="text-xs font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
          >
            <span>Manage All</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {projectsLoading ? (
          <div className="py-8 text-center text-xs font-mono text-slate-400 animate-pulse">
            Querying PostgreSQL database...
          </div>
        ) : projectsData?.items && projectsData.items.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-border/80 text-slate-400 text-[11px]">
                  <th className="py-2.5 px-3">PROJECT NAME</th>
                  <th className="py-2.5 px-3">TARGET CRS</th>
                  <th className="py-2.5 px-3">STATUS</th>
                  <th className="py-2.5 px-3">CREATED</th>
                  <th className="py-2.5 px-3 text-right">ACTION</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {projectsData.items.map((project) => (
                  <tr key={project.id} className="hover:bg-surface-800/40 transition-colors">
                    <td className="py-3 px-3">
                      <Link
                        to={`/projects/${project.id}`}
                        className="font-medium text-slate-200 hover:text-cyan-300"
                      >
                        {project.name}
                      </Link>
                      {project.description && (
                        <div className="text-[11px] text-slate-400 font-sans truncate max-w-sm">
                          {project.description}
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-3 text-slate-300">{project.target_crs}</td>
                    <td className="py-3 px-3">
                      <StatusBadge status={project.status} />
                    </td>
                    <td className="py-3 px-3 text-slate-400">{formatDate(project.created_at)}</td>
                    <td className="py-3 px-3 text-right">
                      <Link
                        to={`/projects/${project.id}`}
                        className="text-cyan-400 hover:underline inline-flex items-center gap-1"
                      >
                        <span>Open</span>
                        <ArrowUpRight className="w-3 h-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-8 border border-dashed border-border rounded text-center">
            <p className="text-xs text-slate-400 font-mono">No projects initialized yet.</p>
            <Link
              to="/projects"
              className="mt-2 inline-flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-300 font-mono"
            >
              <span>+ Create your first project workspace</span>
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
