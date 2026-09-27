import React, { useEffect, useRef, useState, useCallback } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import {
  Layers,
  Crosshair,
  Loader2,
  Compass,
  Eye,
  EyeOff,
  Maximize2,
} from 'lucide-react'
import { useProjectLayers } from '../../hooks/useDatasets'
import { api } from '../../services/api'
import type { MatchDetailResponse, BoundingBox } from '../../types'

interface ReconciliationMapProps {
  projectId: string
  targetCrs: string
  selectedMatch: MatchDetailResponse | null
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

export const ReconciliationMap: React.FC<ReconciliationMapProps> = ({
  projectId,
  targetCrs,
  selectedMatch,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const [mapLoaded, setMapLoaded] = useState(false)
  const [cursorCoords, setCursorCoords] = useState<{ lon: number; lat: number } | null>(null)
  const [currentZoom, setCurrentZoom] = useState<number>(2)
  const [isLoadingLayers, setIsLoadingLayers] = useState(false)

  const { data: layersData } = useProjectLayers(projectId)
  const layers = layersData?.layers || []
  const combinedBounds = layersData?.combined_bounds

  const getBoundsArray = (bbox?: BoundingBox | null): [[number, number], [number, number]] | null => {
    if (!bbox) return null
    return [
      [bbox.min_x, bbox.min_y],
      [bbox.max_x, bbox.max_y],
    ]
  }

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

  // 2. Load background project layers
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapLoaded) return

    let isMounted = true

    const loadBackgroundLayers = async () => {
      setIsLoadingLayers(true)
      try {
        for (const layer of layers) {
          const sourceId = `recon-bg-${layer.id}`
          const fillId = `recon-bg-${layer.id}-fill`
          const lineId = `recon-bg-${layer.id}-line`
          const circleId = `recon-bg-${layer.id}-circle`
          const color = layer.color || '#475569'

          const geojsonData = await api.getDatasetFeaturesGeoJSON(layer.dataset_id, 'canonical')
          if (!isMounted) return

          const existingSource = map.getSource(sourceId) as maplibregl.GeoJSONSource | undefined
          if (existingSource) {
            existingSource.setData(geojsonData as any)
          } else {
            map.addSource(sourceId, {
              type: 'geojson',
              data: geojsonData as any,
            })
          }

          const geomType = layer.geometry_type.toLowerCase()
          if (geomType.includes('polygon')) {
            if (!map.getLayer(fillId)) {
              map.addLayer({
                id: fillId,
                type: 'fill',
                source: sourceId,
                paint: {
                  'fill-color': color,
                  'fill-opacity': 0.15,
                },
              })
            }
            if (!map.getLayer(lineId)) {
              map.addLayer({
                id: lineId,
                type: 'line',
                source: sourceId,
                paint: {
                  'line-color': color,
                  'line-width': 1,
                  'line-opacity': 0.4,
                },
              })
            }
          } else if (geomType.includes('point')) {
            if (!map.getLayer(circleId)) {
              map.addLayer({
                id: circleId,
                type: 'circle',
                source: sourceId,
                paint: {
                  'circle-radius': 4,
                  'circle-color': color,
                  'circle-opacity': 0.4,
                },
              })
            }
          }
        }

        if (combinedBounds && !selectedMatch) {
          const boundsArr = getBoundsArray(combinedBounds)
          if (boundsArr) {
            map.fitBounds(boundsArr, { padding: 60, maxZoom: 16, duration: 1000 })
          }
        }
      } catch (err) {
        console.error('Error loading background layers for reconciliation map:', err)
      } finally {
        if (isMounted) setIsLoadingLayers(false)
      }
    }

    loadBackgroundLayers()

    return () => {
      isMounted = false
    }
  }, [mapLoaded, layers])

  // 3. Highlight Selected Match (Source, Candidate, and Intersection)
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapLoaded) return

    const sourceGeomSourceId = 'highlight-source-geom'
    const candidateGeomSourceId = 'highlight-candidate-geom'
    const intersectionGeomSourceId = 'highlight-intersection-geom'

    // Helper to calculate bbox from geojson geometry coordinates
    const computeGeomBbox = (coords: any): [number, number, number, number] | null => {
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
      const scan = (c: any) => {
        if (typeof c[0] === 'number') {
          minX = Math.min(minX, c[0])
          minY = Math.min(minY, c[1])
          maxX = Math.max(maxX, c[0])
          maxY = Math.max(maxY, c[1])
        } else if (Array.isArray(c)) {
          c.forEach(scan)
        }
      }
      scan(coords)
      if (minX === Infinity) return null
      return [minX, minY, maxX, maxY]
    }

    // Helper to upsert GeoJSON source and render layers
    const updateHighlightLayer = (
      sourceId: string,
      prefix: string,
      geometry: any | null,
      fillColor: string,
      lineColor: string,
      pointColor: string
    ) => {
      const geojsonData = geometry
        ? {
            type: 'FeatureCollection',
            features: [
              {
                type: 'Feature',
                geometry: geometry,
                properties: {},
              },
            ],
          }
        : { type: 'FeatureCollection', features: [] }

      const existingSource = map.getSource(sourceId) as maplibregl.GeoJSONSource | undefined
      if (existingSource) {
        existingSource.setData(geojsonData as any)
      } else {
        map.addSource(sourceId, {
          type: 'geojson',
          data: geojsonData as any,
        })
      }

      // Fill Layer
      const fillId = `${prefix}-fill`
      if (!map.getLayer(fillId)) {
        map.addLayer({
          id: fillId,
          type: 'fill',
          source: sourceId,
          paint: {
            'fill-color': fillColor,
            'fill-opacity': 0.45,
          },
          filter: ['==', '$type', 'Polygon'],
        })
      }

      // Line Layer
      const lineId = `${prefix}-line`
      if (!map.getLayer(lineId)) {
        map.addLayer({
          id: lineId,
          type: 'line',
          source: sourceId,
          paint: {
            'line-color': lineColor,
            'line-width': 3,
            'line-opacity': 0.95,
          },
        })
      }

      // Point Circle Layer
      const circleId = `${prefix}-circle`
      if (!map.getLayer(circleId)) {
        map.addLayer({
          id: circleId,
          type: 'circle',
          source: sourceId,
          paint: {
            'circle-radius': 8,
            'circle-color': pointColor,
            'circle-stroke-width': 2.5,
            'circle-stroke-color': '#ffffff',
            'circle-opacity': 0.95,
          },
          filter: ['==', '$type', 'Point'],
        })
      }
    }

    if (selectedMatch) {
      const srcGeom = selectedMatch.source_feature?.geometry
      const candGeom = selectedMatch.candidate_feature?.geometry
      const interGeom = selectedMatch.intersection_geometry

      // Source in vibrant Cyan
      updateHighlightLayer(
        sourceGeomSourceId,
        'hl-source',
        srcGeom,
        '#06b6d4',
        '#22d3ee',
        '#06b6d4'
      )

      // Candidate color styling based on review status and candidate role
      const reviewStatus = selectedMatch.review_status
      const role = selectedMatch.candidate_role
      let candFillColor = '#f59e0b'
      let candLineColor = '#fbbf24'
      let candPointColor = '#f59e0b'
      let candFillOpacity = 0.45
      let candLineWidth = 3
      let isDashed = false

      if (reviewStatus === 'ACCEPTED') {
        candFillColor = '#059669'
        candLineColor = '#10b981'
        candPointColor = '#10b981'
        candFillOpacity = 0.55
        candLineWidth = 4
        isDashed = false
      } else if (reviewStatus === 'REJECTED') {
        candFillColor = '#e11d48'
        candLineColor = '#f43f5e'
        candPointColor = '#e11d48'
        candFillOpacity = 0.2
        candLineWidth = 2.5
        isDashed = true
      } else if (reviewStatus === 'FLAGGED') {
        candFillColor = '#ea580c'
        candLineColor = '#f97316'
        candPointColor = '#ea580c'
        candFillOpacity = 0.45
        candLineWidth = 3.5
        isDashed = false
      } else if (role === 'BEST') {
        candFillColor = '#f59e0b'
        candLineColor = '#fbbf24'
        candPointColor = '#f59e0b'
        candFillOpacity = 0.5
        candLineWidth = 3.5
      } else if (role === 'AMBIGUOUS') {
        candFillColor = '#ea580c'
        candLineColor = '#f97316'
        candPointColor = '#ea580c'
        candFillOpacity = 0.4
        candLineWidth = 3
        isDashed = true
      } else if (role === 'SECONDARY') {
        candFillColor = '#6366f1'
        candLineColor = '#818cf8'
        candPointColor = '#6366f1'
        candFillOpacity = 0.25
        candLineWidth = 2
      } else if (role === 'CONFLICT') {
        candFillColor = '#ef4444'
        candLineColor = '#f87171'
        candPointColor = '#ef4444'
        candFillOpacity = 0.4
        candLineWidth = 3
      }

      // Candidate layer
      updateHighlightLayer(
        candidateGeomSourceId,
        'hl-candidate',
        candGeom,
        candFillColor,
        candLineColor,
        candPointColor
      )

      // Apply dynamic paint properties for candidate line/fill
      const candLineLayerId = 'hl-candidate-line'
      if (map.getLayer(candLineLayerId)) {
        map.setPaintProperty(candLineLayerId, 'line-color', candLineColor)
        map.setPaintProperty(candLineLayerId, 'line-width', candLineWidth)
        if (isDashed) {
          map.setPaintProperty(candLineLayerId, 'line-dasharray', [2, 2])
        } else {
          map.setPaintProperty(candLineLayerId, 'line-dasharray', [1, 0])
        }
      }
      const candFillLayerId = 'hl-candidate-fill'
      if (map.getLayer(candFillLayerId)) {
        map.setPaintProperty(candFillLayerId, 'fill-color', candFillColor)
        map.setPaintProperty(candFillLayerId, 'fill-opacity', candFillOpacity)
      }

      // Shared intersection in vibrant Emerald
      updateHighlightLayer(
        intersectionGeomSourceId,
        'hl-intersection',
        interGeom,
        '#10b981',
        '#34d399',
        '#10b981'
      )

      // Calculate combined bounding box of source + candidate
      let overallMinX = Infinity, overallMinY = Infinity, overallMaxX = -Infinity, overallMaxY = -Infinity

      if (srcGeom && srcGeom.coordinates) {
        const b = computeGeomBbox(srcGeom.coordinates)
        if (b) {
          overallMinX = Math.min(overallMinX, b[0])
          overallMinY = Math.min(overallMinY, b[1])
          overallMaxX = Math.max(overallMaxX, b[2])
          overallMaxY = Math.max(overallMaxY, b[3])
        }
      }
      if (candGeom && candGeom.coordinates) {
        const b = computeGeomBbox(candGeom.coordinates)
        if (b) {
          overallMinX = Math.min(overallMinX, b[0])
          overallMinY = Math.min(overallMinY, b[1])
          overallMaxX = Math.max(overallMaxX, b[2])
          overallMaxY = Math.max(overallMaxY, b[3])
        }
      }

      if (overallMinX !== Infinity) {
        // If it's a point or zero-width bbox, expand slightly
        if (overallMinX === overallMaxX && overallMinY === overallMaxY) {
          overallMinX -= 0.001
          overallMaxX += 0.001
          overallMinY -= 0.001
          overallMaxY += 0.001
        }
        map.fitBounds(
          [
            [overallMinX, overallMinY],
            [overallMaxX, overallMaxY],
          ],
          { padding: 120, maxZoom: 17, duration: 800 }
        )
      }
    } else {
      // Clear highlights
      updateHighlightLayer(sourceGeomSourceId, 'hl-source', null, '', '', '')
      updateHighlightLayer(candidateGeomSourceId, 'hl-candidate', null, '', '', '')
      updateHighlightLayer(intersectionGeomSourceId, 'hl-intersection', null, '', '', '')
    }
  }, [mapLoaded, selectedMatch])

  const fitToProject = () => {
    const map = mapRef.current
    if (!map || !combinedBounds) return

    const boundsArr = getBoundsArray(combinedBounds)
    if (boundsArr) {
      map.fitBounds(boundsArr, { padding: 80, maxZoom: 16, duration: 800 })
    }
  }

  return (
    <div className="relative flex-1 h-full min-h-[420px] bg-surface-950 flex flex-col font-mono select-none overflow-hidden">
      {/* Map Sub-Toolbar */}
      <div className="h-9 bg-surface-900/90 backdrop-blur border-b border-border px-3 flex items-center justify-between z-10 text-[11px]">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-slate-300 font-semibold">
            <Compass className="w-3.5 h-3.5 text-cyan-400" />
            <span>Target CRS:</span>
            <span className="text-cyan-300 font-bold">{targetCrs}</span>
          </div>
          {isLoadingLayers && (
            <div className="flex items-center gap-1 text-cyan-400 text-[10px] animate-pulse">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>Rendering context layers...</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Visual Legend */}
          <div className="hidden sm:flex items-center gap-3 px-2 py-0.5 rounded bg-surface-950/80 border border-border text-[10px]">
            <div className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-sm bg-cyan-400 border border-cyan-300" />
              <span className="text-slate-300 font-medium">Source</span>
            </div>
            <div className="flex items-center gap-1">
              {selectedMatch?.review_status === 'ACCEPTED' ? (
                <>
                  <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500 border border-emerald-400" />
                  <span className="text-emerald-300 font-bold">✓ Accepted</span>
                </>
              ) : selectedMatch?.review_status === 'REJECTED' ? (
                <>
                  <span className="w-2.5 h-2.5 rounded-sm bg-rose-600 border border-rose-400 border-dashed" />
                  <span className="text-rose-300 font-bold">✗ Rejected</span>
                </>
              ) : selectedMatch?.review_status === 'FLAGGED' ? (
                <>
                  <span className="w-2.5 h-2.5 rounded-sm bg-orange-500 border border-orange-400" />
                  <span className="text-orange-300 font-bold">⚑ Flagged</span>
                </>
              ) : selectedMatch?.candidate_role === 'BEST' ? (
                <>
                  <span className="w-2.5 h-2.5 rounded-sm bg-amber-400 border border-amber-300" />
                  <span className="text-amber-300 font-bold">★ Best</span>
                </>
              ) : selectedMatch?.candidate_role === 'AMBIGUOUS' ? (
                <>
                  <span className="w-2.5 h-2.5 rounded-sm bg-orange-500 border border-orange-400 border-dashed" />
                  <span className="text-orange-300 font-bold">Ambiguous (Tied)</span>
                </>
              ) : selectedMatch?.candidate_role === 'SECONDARY' ? (
                <>
                  <span className="w-2.5 h-2.5 rounded-sm bg-indigo-500 border border-indigo-400" />
                  <span className="text-indigo-300 font-medium">Secondary</span>
                </>
              ) : selectedMatch?.candidate_role === 'CONFLICT' ? (
                <>
                  <span className="w-2.5 h-2.5 rounded-sm bg-red-500 border border-red-400" />
                  <span className="text-red-300 font-bold">Conflict</span>
                </>
              ) : (
                <>
                  <span className="w-2.5 h-2.5 rounded-sm bg-amber-400 border border-amber-300" />
                  <span className="text-slate-300 font-medium">Candidate</span>
                </>
              )}
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-sm bg-emerald-400 border border-emerald-300" />
              <span className="text-slate-300 font-medium">Overlap</span>
            </div>
          </div>

          {combinedBounds && (
            <button
              onClick={fitToProject}
              title="Reset Extent"
              className="inline-flex items-center gap-1 px-2 py-1 rounded bg-surface-850 hover:bg-surface-800 border border-border text-slate-300 hover:text-cyan-300 transition-colors text-[10px]"
            >
              <Crosshair className="w-3 h-3 text-cyan-400" />
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
            <span className="text-slate-200">
              {cursorCoords.lon.toFixed(4)}°, {cursorCoords.lat.toFixed(4)}°
            </span>
          ) : (
            <span className="text-slate-600">--</span>
          )}
          <span className="text-slate-600">|</span>
          <span>ZOOM:</span>
          <span className="text-slate-200">{currentZoom}</span>
        </div>

        <div className="flex items-center gap-1.5 text-emerald-400">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span>Real-time PostGIS GeoJSON Highlight</span>
        </div>
      </div>
    </div>
  )
}
