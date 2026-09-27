import React, { useState, useRef } from 'react'
import {
  UploadCloud,
  FileSpreadsheet,
  FileCode,
  Archive,
  Layers,
  X,
  AlertCircle,
  Loader2,
  CheckCircle2,
} from 'lucide-react'
import { useUploadDataset } from '../../hooks/useDatasets'
import { formatBytes } from '../../lib/utils'

interface DatasetUploadModalProps {
  projectId: string
  isOpen: boolean
  onClose: () => void
}

export const DatasetUploadModal: React.FC<DatasetUploadModalProps> = ({
  projectId,
  isOpen,
  onClose,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [customName, setCustomName] = useState('')
  const [customCrs, setCustomCrs] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const uploadMutation = useUploadDataset(projectId)

  if (!isOpen) return null

  const handleFileChange = (file: File) => {
    setUploadError(null)
    setSelectedFile(file)
    if (!customName) {
      // Auto-populate name without extension
      const baseName = file.name.replace(/\.[^/.]+$/, '')
      setCustomName(baseName)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileChange(e.dataTransfer.files[0])
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedFile) {
      setUploadError('Please select a geospatial file to upload.')
      return
    }

    setUploadError(null)
    try {
      await uploadMutation.mutateAsync({
        file: selectedFile,
        name: customName,
        crs: customCrs,
      })
      handleClose()
    } catch (err: any) {
      const msg =
        err.response?.data?.error?.message ||
        err.message ||
        'Failed to upload and profile dataset.'
      setUploadError(msg)
    }
  }

  const handleClose = () => {
    setSelectedFile(null)
    setCustomName('')
    setCustomCrs('')
    setUploadError(null)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="relative w-full max-w-xl bg-surface-900 border border-border rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-surface-950/60">
          <div className="flex items-center gap-2">
            <UploadCloud className="w-5 h-5 text-cyan-400" />
            <h2 className="text-base font-semibold font-mono text-slate-100 tracking-wide">
              INGEST GEOSPATIAL DATASET
            </h2>
          </div>
          <button
            onClick={handleClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-surface-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5 overflow-y-auto">
          {uploadError && (
            <div className="p-3 rounded-lg bg-rose-950/50 border border-rose-800/80 text-rose-300 text-xs flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <div className="leading-relaxed">{uploadError}</div>
            </div>
          )}

          {/* Drag & Drop Zone */}
          <div
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all duration-200 flex flex-col items-center justify-center gap-3 ${
              dragOver
                ? 'border-cyan-500 bg-cyan-950/20'
                : selectedFile
                ? 'border-emerald-600/70 bg-emerald-950/10'
                : 'border-border/80 hover:border-slate-500 bg-surface-950/40 hover:bg-surface-850'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept=".geojson,.json,.csv,.gpkg,.zip"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  handleFileChange(e.target.files[0])
                }
              }}
            />

            {selectedFile ? (
              <div className="flex flex-col items-center gap-2">
                <CheckCircle2 className="w-8 h-8 text-emerald-400" />
                <div className="text-sm font-medium text-slate-100 font-mono">
                  {selectedFile.name}
                </div>
                <div className="text-xs text-slate-400 font-mono">
                  {formatBytes(selectedFile.size)} • Click to replace
                </div>
              </div>
            ) : (
              <>
                <div className="w-12 h-12 rounded-full bg-surface-800 border border-border flex items-center justify-center text-slate-400">
                  <UploadCloud className="w-6 h-6 text-cyan-400" />
                </div>
                <div>
                  <div className="text-sm font-medium text-slate-200">
                    Click to browse or drag & drop geospatial file
                  </div>
                  <div className="text-xs text-slate-400 mt-1">
                    Maximum upload size: 50 MB
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Supported Format Pills */}
          <div className="space-y-1.5">
            <span className="text-[11px] font-mono uppercase tracking-wider text-slate-400">
              Supported Formats
            </span>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono">
              <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-surface-950 border border-border text-slate-300">
                <FileCode className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                <span>GeoJSON (.geojson)</span>
              </div>
              <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-surface-950 border border-border text-slate-300">
                <Archive className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                <span>Shapefile (.zip)</span>
              </div>
              <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-surface-950 border border-border text-slate-300">
                <Layers className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                <span>GeoPackage (.gpkg)</span>
              </div>
              <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-surface-950 border border-border text-slate-300">
                <FileSpreadsheet className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                <span>CSV + Lat/Lon</span>
              </div>
            </div>
          </div>

          {/* Form Inputs */}
          <div className="space-y-3 pt-2">
            <div>
              <label className="block text-xs font-mono text-slate-300 mb-1">
                Dataset Name (Optional)
              </label>
              <input
                type="text"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                placeholder="e.g. Cadastral Survey 2026"
                className="w-full px-3 py-2 rounded-lg bg-surface-950 border border-border text-slate-200 text-xs focus:outline-none focus:border-cyan-500 font-mono placeholder:text-slate-500"
              />
            </div>

            <div>
              <label className="block text-xs font-mono text-slate-300 mb-1">
                Target / Override CRS (Optional)
              </label>
              <input
                type="text"
                value={customCrs}
                onChange={(e) => setCustomCrs(e.target.value)}
                placeholder="e.g. EPSG:4326 (Default for CSV)"
                className="w-full px-3 py-2 rounded-lg bg-surface-950 border border-border text-slate-200 text-xs focus:outline-none focus:border-cyan-500 font-mono placeholder:text-slate-500"
              />
              <span className="text-[11px] text-slate-400 mt-1 block">
                GeoJSON and Shapefiles auto-detect CRS. For CSV files, defaults to EPSG:4326 (WGS84).
              </span>
            </div>
          </div>

          {/* Footer Controls */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
            <button
              type="button"
              onClick={handleClose}
              disabled={uploadMutation.isPending}
              className="px-4 py-2 rounded-lg border border-border text-slate-300 hover:bg-surface-800 text-xs font-mono font-medium transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!selectedFile || uploadMutation.isPending}
              className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-mono font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {uploadMutation.isPending ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Ingesting & Profiling...</span>
                </>
              ) : (
                <>
                  <UploadCloud className="w-3.5 h-3.5" />
                  <span>Start Ingestion</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
