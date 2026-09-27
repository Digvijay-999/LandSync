import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { FolderGit2, Plus, Trash2, ArrowUpRight, Loader2, Globe } from 'lucide-react'
import { useProjects, useCreateProject, useDeleteProject } from '../hooks/useProjects'
import { StatusBadge } from '../components/common/StatusBadge'
import { formatDate } from '../lib/utils'

export const ProjectsPage: React.FC = () => {
  const { data, isLoading } = useProjects()
  const createMutation = useCreateProject()
  const deleteMutation = useDeleteProject()

  const [showModal, setShowModal] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [targetCrs, setTargetCrs] = useState('EPSG:4326')

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return

    await createMutation.mutateAsync({
      name: name.trim(),
      description: description.trim() || undefined,
      target_crs: targetCrs,
    })

    setName('')
    setDescription('')
    setShowModal(false)
  }

  const handleDelete = async (id: string, name: string) => {
    if (window.confirm(`Are you sure you want to delete project "${name}"?`)) {
      await deleteMutation.mutateAsync(id)
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/80 pb-4">
        <div>
          <h1 className="text-xl font-bold font-mono text-slate-100 flex items-center gap-2">
            <FolderGit2 className="w-5 h-5 text-cyan-400" />
            <span>HARMONIZATION WORKSPACES</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Manage geospatial projects, coordinate target reference systems, and tracking pipelines.
          </p>
        </div>

        <button
          onClick={() => setShowModal(true)}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-mono font-medium transition-colors self-start sm:self-auto"
        >
          <Plus className="w-4 h-4" />
          <span>New Project</span>
        </button>
      </div>

      {/* Projects Table */}
      <div className="bg-surface-900 border border-border rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="text-xs font-mono text-slate-400">
            Total Projects: <span className="text-slate-200 font-bold">{data?.total || 0}</span>
          </div>
        </div>

        {isLoading ? (
          <div className="py-12 flex flex-col items-center justify-center gap-2 text-xs font-mono text-slate-400">
            <Loader2 className="w-5 h-5 animate-spin text-cyan-400" />
            <span>Loading projects from database...</span>
          </div>
        ) : data?.items && data.items.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-border text-slate-400 text-[11px]">
                  <th className="py-2.5 px-3">PROJECT NAME</th>
                  <th className="py-2.5 px-3">PROJECT ID</th>
                  <th className="py-2.5 px-3">TARGET CRS</th>
                  <th className="py-2.5 px-3">STATUS</th>
                  <th className="py-2.5 px-3">CREATED</th>
                  <th className="py-2.5 px-3 text-right">ACTIONS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {data.items.map((project) => (
                  <tr key={project.id} className="hover:bg-surface-800/40 transition-colors">
                    <td className="py-3 px-3">
                      <Link
                        to={`/projects/${project.id}`}
                        className="font-semibold text-slate-200 hover:text-cyan-300"
                      >
                        {project.name}
                      </Link>
                      {project.description && (
                        <div className="text-[11px] text-slate-400 font-sans truncate max-w-xs mt-0.5">
                          {project.description}
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-3 text-slate-400 text-[11px]">
                      {project.id.slice(0, 8)}...
                    </td>
                    <td className="py-3 px-3">
                      <span className="inline-flex items-center gap-1 text-slate-300 bg-surface-950 px-2 py-0.5 rounded border border-border">
                        <Globe className="w-3 h-3 text-cyan-400" />
                        <span>{project.target_crs}</span>
                      </span>
                    </td>
                    <td className="py-3 px-3">
                      <StatusBadge status={project.status} />
                    </td>
                    <td className="py-3 px-3 text-slate-400">{formatDate(project.created_at)}</td>
                    <td className="py-3 px-3 text-right space-x-2">
                      <Link
                        to={`/projects/${project.id}`}
                        className="text-cyan-400 hover:text-cyan-300 inline-flex items-center gap-1"
                      >
                        <span>Details</span>
                        <ArrowUpRight className="w-3 h-3" />
                      </Link>
                      <button
                        onClick={() => handleDelete(project.id, project.name)}
                        className="text-slate-400 hover:text-rose-400 p-1"
                        title="Delete project"
                        disabled={deleteMutation.isPending}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-12 border border-dashed border-border rounded-lg text-center space-y-2">
            <FolderGit2 className="w-8 h-8 text-slate-400 mx-auto" />
            <p className="text-xs font-mono text-slate-300">No harmonization workspaces found</p>
            <p className="text-[11px] text-slate-400">
              Create a project to initialize cadastral, GIS, and survey datasets.
            </p>
            <button
              onClick={() => setShowModal(true)}
              className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-mono"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Create Project</span>
            </button>
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-surface-900 border border-border rounded-lg max-w-md w-full p-6 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <h3 className="font-mono text-sm font-bold text-slate-100 uppercase">
                Initialize Harmonization Project
              </h3>
              <button
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-slate-200 text-sm font-mono"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-mono text-slate-300 mb-1">
                  Project Workspace Name *
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Metro Cadastral Survey Q4"
                  className="w-full px-3 py-2 bg-surface-950 border border-border rounded text-xs font-mono text-slate-100 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-xs font-mono text-slate-300 mb-1">
                  Target Coordinate Reference System (CRS)
                </label>
                <select
                  value={targetCrs}
                  onChange={(e) => setTargetCrs(e.target.value)}
                  className="w-full px-3 py-2 bg-surface-950 border border-border rounded text-xs font-mono text-slate-100 focus:outline-none focus:border-cyan-500"
                >
                  <option value="EPSG:4326">EPSG:4326 (WGS 84 - Standard Geographic)</option>
                  <option value="EPSG:3857">EPSG:3857 (Web Mercator)</option>
                  <option value="EPSG:32643">EPSG:32643 (UTM Zone 43N)</option>
                  <option value="EPSG:32644">EPSG:32644 (UTM Zone 44N)</option>
                  <option value="EPSG:2193">EPSG:2193 (NZGD2000)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-mono text-slate-300 mb-1">
                  Description
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Optional details regarding dataset sources and survey bounds..."
                  rows={3}
                  className="w-full px-3 py-2 bg-surface-950 border border-border rounded text-xs font-sans text-slate-100 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-border">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-3 py-1.5 rounded border border-border text-xs font-mono text-slate-400 hover:text-slate-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="px-4 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-mono font-medium disabled:opacity-50 flex items-center gap-1.5"
                >
                  {createMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>Create Workspace</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
