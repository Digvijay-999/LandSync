import React, { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import {
  Layers,
  Crosshair,
  Loader2,
  Eye,
  EyeOff,
  Maximize2,
  ShieldCheck,
  Compass,
} from 'lucide-react'
import { api } from '../../services/api'
import { useProjectLayers } from '../../hooks/useDatasets'
import type { UnifiedRecordDetail, BoundingBox } from '../../types'

interface UnifiedRecordMapProps {
  projectId: string
  targetCrs: string
  selectedRecord: UnifiedRecordDetail | null
  showSourceFootprints: boolean
  onToggleSourceFootprints: () => void
}

const DARK_MAP_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    'carto-dark': {
      type: 'raster',
      tiles: [
        'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
        'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
        'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
        'https://d.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png',
      ],
      tileSize: 256,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    },
  },
  layers: [
    {
      id: 'carto-dark-base',
      type: 'raster',
      source: 'carto-dark',
      minzoom: 0,
      maxzoom: 20,
    },
  ],
}

function computeGeomBbox(coords: any): [number, number, number, number] | null {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  function traverse(c: any) {
    if (typeof c[0] === 'number' && typeof c[1] === 'number') {
      const x = c[0], y = c[1]
      if (x < minX) minX = x
      if (y < minY) minY = y
      if (x > maxX) maxX = x
      if (y > maxY) maxY = y
    } else if (Array.isArray(c)) {
      for (const item of c) traverse(item)
    }
  }
  traverse(coords)
  return minX !== Infinity ? [minX, minY, maxX, maxY] : null
}

export const UnifiedRecordMap: React.FC<UnifiedRecordMapProps> = ({
  projectId,
  targetCrs,
  selectedRecord,
  showSourceFootprints,
  onToggleSourceFootprints,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const [mapLoaded, setMapLoaded] = useState(false)
  const [cursorCoords, setCursorCoords] = useState<{ lon: number; lat: number } | null>(null)
  const [currentZoom, setCurrentZoom] = useState<number>(2)

  const { data: layersData } = useProjectLayers(projectId)
  const combinedBounds = layersData?.combined_bounds

  // 1. Initialize MapLibre GL
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: DARK_MAP_STYLE,
      center: [73.8567, 18.5204],
      zoom: 12,
      attributionControl: false,
    })

    map.addControl(new maplibregl.NavigationControl({ showCompass: true, showZoom: true }), 'top-right')
    map.addControl(
      new maplibregl.AttributionControl({ compact: true, customAttribution: 'LandSync Spatial Engine' }),
      'bottom-right'
    )

    map.on('load', () => {
      setMapLoaded(true)
      map.resize()
    })

    map.on('mousemove', (e: maplibregl.MapMouseEvent) => {
      setCursorCoords({
        lon: Number(e.lngLat.lng.toFixed(6)),
        lat: Number(e.lngLat.lat.toFixed(6)),
      })
    })

    map.on('zoom', () => {
      setCurrentZoom(Number(map.getZoom().toFixed(2)))
    })

    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
      setMapLoaded(false)
    }
  }, [])

  // 2. Render Canonical Geometry and Sources
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapLoaded) return

    const canonSourceId = 'ulr-canonical-source'
    const sourcesSourceId = 'ulr-sources-source'

    const updateSourceData = (sId: string, features: any[]) => {
      const fc = { type: 'FeatureCollection', features }
      const existing = map.getSource(sId) as maplibregl.GeoJSONSource | undefined
      if (existing) {
        existing.setData(fc as any)
      } else {
        map.addSource(sId, { type: 'geojson', data: fc as any })
      }
    }

    // Prepare Canonical Feature
    const canonFeatures: any[] = []
    if (selectedRecord && selectedRecord.canonical_geometry) {
      canonFeatures.push({
        type: 'Feature',
        id: selectedRecord.id,
        geometry: selectedRecord.canonical_geometry,
        properties: {
          identifier: selectedRecord.record_identifier,
          status: selectedRecord.status,
          role: selectedRecord.geometry_source_role || 'CANONICAL',
        },
      })
    }
    updateSourceData(canonSourceId, canonFeatures)

    // Prepare Contributing Source Features
    const sourceFeatures: any[] = []
    if (selectedRecord && showSourceFootprints && selectedRecord.sources) {
      for (const s of selectedRecord.sources) {
        if (s.geometry) {
          sourceFeatures.push({
            type: 'Feature',
            id: s.id,
            geometry: s.geometry,
            properties: {
              role: s.source_role,
              dataset_name: s.dataset_name,
              identifier: s.source_identifier,
            },
          })
        }
      }
    }
    updateSourceData(sourcesSourceId, sourceFeatures)

    // Layers for Contributing Sources
    if (!map.getLayer('ulr-sources-fill')) {
      map.addLayer({
        id: 'ulr-sources-fill',
        type: 'fill',
        source: sourcesSourceId,
        paint: {
          'fill-color': [
            'match',
            ['get', 'role'],
            'CADASTRAL', '#06b6d4',
            'DRONE', '#f59e0b',
            'MUNICIPAL', '#6366f1',
            '#94a3b8',
          ],
          'fill-opacity': 0.25,
        },
        filter: ['==', '$type', 'Polygon'],
      })
    }
    if (!map.getLayer('ulr-sources-line')) {
      map.addLayer({
        id: 'ulr-sources-line',
        type: 'line',
        source: sourcesSourceId,
        paint: {
          'line-color': [
            'match',
            ['get', 'role'],
            'CADASTRAL', '#22d3ee',
            'DRONE', '#fbbf24',
            'MUNICIPAL', '#818cf8',
            '#cbd5e1',
          ],
          'line-width': 2,
          'line-dasharray': [2, 2],
        },
      })
    }

    // Layers for Canonical Geometry
    if (!map.getLayer('ulr-canonical-fill')) {
      map.addLayer({
        id: 'ulr-canonical-fill',
        type: 'fill',
        source: canonSourceId,
        paint: {
          'fill-color': '#10b981',
          'fill-opacity': 0.45,
        },
        filter: ['==', '$type', 'Polygon'],
      })
    }
    if (!map.getLayer('ulr-canonical-line')) {
      map.addLayer({
        id: 'ulr-canonical-line',
        type: 'line',
        source: canonSourceId,
        paint: {
          'line-color': '#34d399',
          'line-width': 3.5,
          'line-opacity': 0.95,
        },
      })
    }
    if (!map.getLayer('ulr-canonical-circle')) {
      map.addLayer({
        id: 'ulr-canonical-circle',
        type: 'circle',
        source: canonSourceId,
        paint: {
          'circle-radius': 9,
          'circle-color': '#10b981',
          'circle-stroke-width': 2.5,
          'circle-stroke-color': '#ffffff',
        },
        filter: ['==', '$type', 'Point'],
      })
    }

    // Zoom/Fit to selected record bounds
    if (selectedRecord && selectedRecord.canonical_geometry?.coordinates) {
      const b = computeGeomBbox(selectedRecord.canonical_geometry.coordinates)
      if (b) {
        let [minX, minY, maxX, maxY] = b
        if (minX === maxX && minY === maxY) {
          minX -= 0.001
          maxX += 0.001
          minY -= 0.001
          maxY += 0.001
        }
        map.fitBounds(
          [
            [minX, minY],
            [maxX, maxY],
          ],
          { padding: 120, maxZoom: 17, duration: 800 }
        )
      }
    }
  }, [mapLoaded, selectedRecord, showSourceFootprints])

  const fitToProject = () => {
    const map = mapRef.current
    if (!map || !combinedBounds) return
    map.fitBounds(
      [
        [combinedBounds.min_x, combinedBounds.min_y],
        [combinedBounds.max_x, combinedBounds.max_y],
      ],
      { padding: 60, maxZoom: 16, duration: 800 }
    )
  }

  return (
    <div className="relative w-full h-full flex flex-col bg-surface-950 font-mono select-none overflow-hidden">
      {/* Top Map Control Bar */}
      <div className="absolute top-3 left-3 right-14 z-10 flex items-center justify-between pointer-events-none">
        <div className="flex items-center gap-2 pointer-events-auto">
          {selectedRecord && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-surface-900/90 border border-border backdrop-blur-sm text-xs shadow-lg">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              <span className="font-bold text-slate-200">{selectedRecord.record_identifier}</span>
              <span className="text-slate-500">•</span>
              <span
                className={`px-1.5 py-0.2 rounded text-[10px] font-bold uppercase ${
                  selectedRecord.status === 'ACTIVE'
                    ? 'bg-emerald-950 text-emerald-300 border border-emerald-600'
                    : selectedRecord.status === 'CONFLICT'
                    ? 'bg-red-950 text-red-300 border border-red-600'
                    : 'bg-amber-950 text-amber-300 border border-amber-600'
                }`}
              >
                {selectedRecord.status}
              </span>
            </div>
          )}
        </div>

        {/* Action Controls & Legend */}
        <div className="flex items-center gap-2 pointer-events-auto">
          {/* Toggle Source Footprints */}
          <button
            onClick={onToggleSourceFootprints}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-semibold border transition-all ${
              showSourceFootprints
                ? 'bg-cyan-950 text-cyan-200 border-cyan-600 shadow-sm'
                : 'bg-surface-900/90 text-slate-400 border-border hover:bg-surface-850 hover:text-slate-200'
            }`}
            title="Toggle contributing source footprint outlines"
          >
            {showSourceFootprints ? <Eye className="w-3.5 h-3.5 text-cyan-400" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span>Source Footprints</span>
          </button>

          {/* Visual Legend */}
          <div className="hidden sm:flex items-center gap-3 px-2.5 py-1 rounded bg-surface-950/90 border border-border text-[10px]">
            <div className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-sm bg-emerald-400 border border-emerald-300" />
              <span className="text-slate-300 font-medium">Canonical</span>
            </div>
            {showSourceFootprints && (
              <>
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-sm bg-cyan-400 border border-cyan-300" />
                  <span className="text-slate-300">Cadastral</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-sm bg-amber-400 border border-amber-300" />
                  <span className="text-slate-300">Drone</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-sm bg-indigo-400 border border-indigo-300" />
                  <span className="text-slate-300">Municipal</span>
                </div>
              </>
            )}
          </div>

          {combinedBounds && (
            <button
              onClick={fitToProject}
              title="Reset Extent"
              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded bg-surface-900/90 hover:bg-surface-850 border border-border text-slate-300 hover:text-cyan-300 transition-colors text-xs"
            >
              <Crosshair className="w-3.5 h-3.5 text-cyan-400" />
              <span>Extent</span>
            </button>
          )}
        </div>
      </div>

      {/* MapLibre Canvas Container */}
      <div className="relative flex-1 w-full h-full overflow-hidden">
        <div ref={mapContainerRef} className="absolute inset-0 w-full h-full" />
      </div>

      {/* Bottom Map Status Bar */}
      <div className="h-6 bg-surface-950 border-t border-border px-3 flex items-center justify-between text-[10px] text-slate-400 z-10">
        <div className="flex items-center gap-2">
          <span>CURSOR:</span>
          {cursorCoords ? (
            <span className="text-slate-200 font-mono">
              {cursorCoords.lon.toFixed(4)}°, {cursorCoords.lat.toFixed(4)}°
            </span>
          ) : (
            <span className="text-slate-600">--</span>
          )}
          <span className="text-slate-600">|</span>
          <span>ZOOM:</span>
          <span className="text-slate-200 font-mono">{currentZoom}</span>
        </div>

        <div className="flex items-center gap-1.5 text-emerald-400 font-mono">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span>PostGIS Unified Canonical Layer ({targetCrs})</span>
        </div>
      </div>
    </div>
  )
}
