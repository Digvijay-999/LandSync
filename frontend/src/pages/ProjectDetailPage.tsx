import React, { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft,
  Globe,
  Calendar,
  Clock,
  Database,
  Layers,
  UploadCloud,
  FileCode,
  FileSpreadsheet,
  Archive,
  Eye,
  Trash2,
  Loader2,
  CheckCircle2,
  AlertCircle,
  HardDrive,
  Activity,
  GitMerge,
  ShieldCheck,
} from 'lucide-react'
import { useProject } from '../hooks/useProjects'
import { useProjectDatasets, useDeleteDataset } from '../hooks/useDatasets'
import { StatusBadge } from '../components/common/StatusBadge'
import { PipelineIndicator } from '../components/common/PipelineIndicator'
import { DatasetUploadModal } from '../components/datasets/DatasetUploadModal'
import { DatasetProfileModal } from '../components/datasets/DatasetProfileModal'
import { MapWorkspace } from '../components/map/MapWorkspace'
import { formatDate, formatBytes } from '../lib/utils'
import type { Dataset } from '../types'

export const ProjectDetailPage: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>()
  const { data: project, isLoading: projectLoading, isError } = useProject(projectId)
  const { data: datasetsData, isLoading: datasetsLoading } = useProjectDatasets(projectId)
  const deleteMutation = useDeleteDataset(projectId!)

  const [activeTab, setActiveTab] = useState<'map' | 'datasets' | 'pipeline'>('map')
  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const [selectedDatasetForProfile, setSelectedDatasetForProfile] = useState<Dataset | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  if (projectLoading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center gap-3 text-xs font-mono text-slate-400">
        <Loader2 className="w-6 h-6 animate-spin text-cyan-400" />
        <span>Loading workspace metadata...</span>
      </div>
    )
  }

  if (isError || !project) {
    return (
      <div className="max-w-xl mx-auto py-16 text-center space-y-4">
        <div className="text-rose-400 font-mono text-sm">Project Workspace Not Found</div>
        <p className="text-xs text-slate-400">
          The requested project ID <span className="font-mono text-slate-300">{projectId}</span> does not exist in the database.
        </p>
        <Link
          to="/projects"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-surface-900 border border-border text-xs font-mono text-cyan-400"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Return to Projects</span>
        </Link>
      </div>
    )
  }

  const datasets = datasetsData?.items || []

  const handleDelete = async (datasetId: string, name: string) => {
    if (window.confirm(`Are you sure you want to delete dataset "${name}"? Physical files and profile metadata will be removed.`)) {
      setDeletingId(datasetId)
      try {
        await deleteMutation.mutateAsync(datasetId)
      } finally {
        setDeletingId(null)
      }
    }
  }

  const getFormatIcon = (format: string) => {
    switch (format.toLowerCase()) {
      case 'geojson':
        return <FileCode className="w-3.5 h-3.5 text-cyan-400" />
      case 'shapefile':
        return <Archive className="w-3.5 h-3.5 text-amber-400" />
      case 'geopackage':
        return <Layers className="w-3.5 h-3.5 text-emerald-400" />
      case 'csv':
        return <FileSpreadsheet className="w-3.5 h-3.5 text-blue-400" />
      default:
        return <Database className="w-3.5 h-3.5 text-slate-400" />
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Navigation breadcrumb */}
      <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
        <Link to="/projects" className="hover:text-cyan-300 flex items-center gap-1">
          <ArrowLeft className="w-3 h-3" />
          <span>Projects</span>
        </Link>
        <span>/</span>
        <span className="text-slate-200 truncate">{project.name}</span>
      </div>

      {/* Project Overview Header Card */}
      <div className="bg-surface-900 border border-border rounded-lg p-6">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 border-b border-border/80 pb-5">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-bold font-mono text-slate-100">{project.name}</h1>
              <StatusBadge status={project.status} />
            </div>
            <p className="text-xs text-slate-400 max-w-2xl font-sans">
              {project.description || 'No description provided for this harmonization workspace.'}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 text-xs font-mono">
            <div className="px-2.5 py-1 rounded bg-surface-950 border border-border text-slate-300 flex items-center gap-1.5">
              <Globe className="w-3.5 h-3.5 text-cyan-400" />
              <span>Target CRS: {project.target_crs}</span>
            </div>
            <Link
              to={`/projects/${projectId}/reconciliation`}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-950 hover:bg-surface-850 border border-cyan-700/80 text-cyan-300 font-semibold transition-all shadow-sm"
            >
              <GitMerge className="w-3.5 h-3.5 text-cyan-400" />
              <span>Reconciliation Workspace</span>
            </Link>
            <Link
              to={`/projects/${projectId}/unified-records`}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-950 hover:bg-surface-850 border border-emerald-700/80 text-emerald-300 font-semibold transition-all shadow-sm"
            >
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              <span>Unified Records</span>
            </Link>
            <button
              onClick={() => setIsUploadOpen(true)}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-semibold transition-colors"
            >
              <UploadCloud className="w-3.5 h-3.5" />
              <span>Upload Dataset</span>
            </button>
          </div>
        </div>

        {/* Metadata Details Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-4 text-xs font-mono">
          <div>
            <span className="text-slate-400 block text-[11px]">WORKSPACE ID</span>
            <span className="text-slate-200 select-all">{project.id}</span>
          </div>
          <div>
            <span className="text-slate-400 block text-[11px]">CREATED AT</span>
            <span className="text-slate-200 flex items-center gap-1">
              <Calendar className="w-3 h-3 text-slate-400" />
              {formatDate(project.created_at)}
            </span>
          </div>
          <div>
            <span className="text-slate-400 block text-[11px]">TOTAL DATASETS</span>
            <span className="text-cyan-400 font-bold">{datasets.length} Ingested</span>
          </div>
          <div>
            <span className="text-slate-400 block text-[11px]">SPATIAL ENGINE</span>
            <span className="text-emerald-400">PostGIS 3.4+ Enabled</span>
          </div>
        </div>
      </div>

      {/* Workspace Navigation Tabs */}
      <div className="flex items-center gap-3 border-b border-border pb-3 text-xs font-mono">
        <button
          onClick={() => setActiveTab('map')}
          className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-lg font-semibold transition-all ${
            activeTab === 'map'
              ? 'bg-cyan-600 text-white shadow-lg shadow-cyan-950/40 border border-cyan-500'
              : 'bg-surface-900 border border-border text-slate-400 hover:text-slate-200 hover:bg-surface-850'
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>Interactive Map Workspace</span>
          <span className="px-1.5 py-0.2 rounded bg-black/40 text-[10px] text-cyan-200">
            {datasets.filter((d) => d.status === 'ready').length} layers
          </span>
        </button>

        <button
          onClick={() => setActiveTab('datasets')}
          className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-lg font-semibold transition-all ${
            activeTab === 'datasets'
              ? 'bg-cyan-600 text-white shadow-lg shadow-cyan-950/40 border border-cyan-500'
              : 'bg-surface-900 border border-border text-slate-400 hover:text-slate-200 hover:bg-surface-850'
          }`}
        >
          <Database className="w-4 h-4" />
          <span>Vector Datasets</span>
          <span className="px-1.5 py-0.2 rounded bg-black/40 text-[10px] text-cyan-200">
            {datasets.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab('pipeline')}
          className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-lg font-semibold transition-all ${
            activeTab === 'pipeline'
              ? 'bg-cyan-600 text-white shadow-lg shadow-cyan-950/40 border border-cyan-500'
              : 'bg-surface-900 border border-border text-slate-400 hover:text-slate-200 hover:bg-surface-850'
          }`}
        >
          <GitMerge className="w-4 h-4" />
          <span>Pipeline & Harmonization</span>
        </button>
      </div>

      {/* TAB 1: INTERACTIVE MAP WORKSPACE */}
      {activeTab === 'map' && (
        <div className="space-y-4">
          <MapWorkspace
            projectId={project.id}
            projectName={project.name}
            targetCrs={project.target_crs}
          />
        </div>
      )}

      {/* TAB 2: DATASETS SECTION */}
      {activeTab === 'datasets' && (
        <div className="bg-surface-900 border border-border rounded-xl overflow-hidden">
          {/* Section Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-surface-950/60">
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-cyan-400" />
              <h2 className="text-sm font-bold font-mono text-slate-100 tracking-wide uppercase">
                Ingested Vector Datasets
              </h2>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-surface-850 text-cyan-300 border border-border">
                {datasets.length}
              </span>
            </div>

            <button
              onClick={() => setIsUploadOpen(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-950/70 border border-cyan-800 text-cyan-300 text-xs font-mono font-medium hover:bg-cyan-900/60 transition-colors"
            >
              <UploadCloud className="w-3.5 h-3.5" />
              <span>Ingest New Dataset</span>
            </button>
          </div>

          {/* Datasets Content */}
          {datasetsLoading ? (
            <div className="py-12 flex flex-col items-center justify-center gap-2 text-xs font-mono text-slate-400">
              <Loader2 className="w-5 h-5 animate-spin text-cyan-400" />
              <span>Loading datasets...</span>
            </div>
          ) : datasets.length === 0 ? (
            /* Empty State */
            <div className="py-16 px-6 text-center max-w-md mx-auto space-y-4">
              <div className="w-14 h-14 rounded-2xl bg-surface-950 border border-border flex items-center justify-center mx-auto text-slate-500">
                <UploadCloud className="w-7 h-7 text-cyan-500/70" />
              </div>
              <div>
                <h3 className="text-sm font-semibold font-mono text-slate-200">
                  No Datasets Ingested Yet
                </h3>
                <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                  Add Cadastral GeoJSON, Municipal GIS shapefiles (.zip), GeoPackage (.gpkg), or CSV coordinate registers to begin profiling and harmonization.
                </p>
              </div>
              <button
                onClick={() => setIsUploadOpen(true)}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-mono font-semibold transition-colors shadow-lg shadow-cyan-950/50"
              >
                <UploadCloud className="w-4 h-4" />
                <span>Upload Geospatial Dataset</span>
              </button>
            </div>
          ) : (
            /* Datasets Table */
            <div className="overflow-x-auto">
              <table className="w-full text-left font-mono text-xs">
                <thead className="bg-surface-950/80 border-b border-border text-[11px] text-slate-400">
                  <tr>
                    <th className="py-3 px-4 font-semibold">Dataset Name & File</th>
                    <th className="py-3 px-4 font-semibold">Format</th>
                    <th className="py-3 px-4 font-semibold">Geometry</th>
                    <th className="py-3 px-4 font-semibold">Features</th>
                    <th className="py-3 px-4 font-semibold">Detected CRS</th>
                    <th className="py-3 px-4 font-semibold">Size</th>
                    <th className="py-3 px-4 font-semibold">Ingested</th>
                    <th className="py-3 px-4 font-semibold text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {datasets.map((ds) => (
                    <tr key={ds.id} className="hover:bg-surface-850/50 transition-colors">
                      <td className="py-3 px-4">
                        <div className="font-semibold text-slate-200 text-xs">{ds.name}</div>
                        <div className="text-[11px] text-slate-400 truncate max-w-xs">
                          {ds.source_filename}
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface-950 border border-border text-[11px] font-semibold text-slate-300">
                          {getFormatIcon(ds.source_format)}
                          <span className="uppercase">{ds.source_format}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 rounded bg-cyan-950/50 border border-cyan-800/80 text-cyan-300 text-[11px]">
                          {ds.geometry_type}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-bold text-slate-200">
                        {ds.feature_count.toLocaleString()}
                      </td>
                      <td className="py-3 px-4 text-slate-300">
                        {ds.detected_crs || 'Unspecified'}
                      </td>
                      <td className="py-3 px-4 text-slate-400">
                        {formatBytes(ds.file_size)}
                      </td>
                      <td className="py-3 px-4 text-slate-400">
                        {formatDate(ds.created_at)}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => setActiveTab('map')}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-surface-950 hover:bg-surface-800 border border-border text-slate-300 hover:text-cyan-300 text-[11px] transition-colors"
                            title="View layer on Map"
                          >
                            <Layers className="w-3 h-3 text-cyan-400" />
                            <span>Map</span>
                          </button>
                          <button
                            onClick={() => setSelectedDatasetForProfile(ds)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-surface-950 hover:bg-surface-800 border border-border text-cyan-400 hover:text-cyan-300 text-[11px] transition-colors"
                            title="Inspect Geometric & Spatial Profile"
                          >
                            <Eye className="w-3 h-3" />
                            <span>Inspect</span>
                          </button>
                          <button
                            onClick={() => handleDelete(ds.id, ds.name)}
                            disabled={deletingId === ds.id}
                            className="p-1 rounded bg-surface-950 hover:bg-rose-950 border border-border hover:border-rose-800 text-slate-400 hover:text-rose-400 transition-colors"
                            title="Delete Dataset"
                          >
                            {deletingId === ds.id ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Trash2 className="w-3.5 h-3.5" />
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: PIPELINE STAGES & DOWNSTREAM ENGINES */}
      {activeTab === 'pipeline' && (
        <div className="space-y-6">
          <PipelineIndicator />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Spatial Matching Engine */}
            <div className="bg-surface-900 border border-border rounded-lg p-4 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs font-mono text-slate-200 font-semibold">
                  <GitMerge className="w-4 h-4 text-purple-400" />
                  <span>Spatial Candidate & Matching Engine</span>
                </div>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface-950 border border-border text-slate-400">
                  Milestone 3 Ready
                </span>
              </div>
              <p className="text-xs text-slate-400">
                PostGIS spatial indexes active (GIST). Candidate parcel pair generation using intersection, containment, and Hausdorff distance.
              </p>
            </div>

            {/* Master Harmonized Records */}
            <div className="bg-surface-900 border border-border rounded-lg p-4 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs font-mono text-slate-200 font-semibold">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span>Unified Harmonized Records</span>
                </div>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface-950 border border-border text-slate-400">
                  Milestone 4 Extension
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Master record resolution, conflict detection, attribute reconciliation, and GeoJSON / FlatGeobuf vector exports.
              </p>
            </div>
          </div>
        </div>
      )}


      {/* Upload Dataset Modal */}
      <DatasetUploadModal
        projectId={projectId!}
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
      />

      {/* Dataset Profile Modal */}
      <DatasetProfileModal
        dataset={selectedDatasetForProfile}
        isOpen={Boolean(selectedDatasetForProfile)}
        onClose={() => setSelectedDatasetForProfile(null)}
      />
    </div>
  )
}
