import React, { useEffect, useRef, useState, useCallback } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import {
  Layers,
  Eye,
  EyeOff,
  Maximize2,
  Crosshair,
  Info,
  X,
  Database,
  FileCode,
  FileSpreadsheet,
  Archive,
  Loader2,
  MapPin,
  RefreshCw,
  Compass,
} from 'lucide-react'
import { useProjectLayers } from '../../hooks/useDatasets'
import { api } from '../../services/api'
import type { ProjectLayer, BoundingBox } from '../../types'

interface MapWorkspaceProps {
  projectId: string
  projectName: string
  targetCrs: string
}

interface SelectedFeatureState {
  id: string
  layerName: string
  geometryType: string
  sourceCrs: string
  targetCrs: string
  properties: Record<string, any>
  coordinatesSummary?: string
}

// Dark technical GIS basemap configuration using CARTO Dark Matter tiles
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

export const MapWorkspace: React.FC<MapWorkspaceProps> = ({
  projectId,
  projectName,
  targetCrs,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const [mapLoaded, setMapLoaded] = useState(false)
  const [cursorCoords, setCursorCoords] = useState<{ lon: number; lat: number } | null>(null)
  const [currentZoom, setCurrentZoom] = useState<number>(2)

  // Layer visibility state (layer.id -> boolean)
  const [layerVisibility, setLayerVisibility] = useState<Record<string, boolean>>({})
  // Selected feature for inspector panel
  const [selectedFeature, setSelectedFeature] = useState<SelectedFeatureState | null>(null)
  // Panel collapsed state
  const [isLayersPanelOpen, setIsLayersPanelOpen] = useState(true)
  const [isLoadingData, setIsLoadingData] = useState(false)

  const { data: layersData, isLoading: layersLoading, refetch: refetchLayers } = useProjectLayers(projectId)
  const layers = layersData?.layers || []
  const combinedBounds = layersData?.combined_bounds

  // Helper to get bbox array for MapLibre fitBounds: [[minX, minY], [maxX, maxY]]
  const getBoundsArray = (bbox?: BoundingBox | null): [[number, number], [number, number]] | null => {
    if (!bbox) return null
    return [
      [bbox.min_x, bbox.min_y],
      [bbox.max_x, bbox.max_y],
    ]
  }

  // 1. Initialize MapLibre GL Map
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: DARK_MAP_STYLE,
      center: [73.8567, 18.5204], // Default center (Pune, India coordinates used in sample datasets)
      zoom: 12,
      attributionControl: false,
    })

    // Add navigation controls
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

  // 2. Sync MapLibre sources & layers when project layers data changes
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapLoaded || layersLoading) return

    let isMounted = true

    const loadLayersIntoMap = async () => {
      setIsLoadingData(true)
      try {
        for (const layer of layers) {
          const sourceId = `src-${layer.id}`
          const fillLayerId = `layer-${layer.id}-fill`
          const lineLayerId = `layer-${layer.id}-line`
          const circleLayerId = `layer-${layer.id}-circle`
          const color = layer.color || '#06b6d4'

          // Fetch canonical GeoJSON data from API
          const geojsonData = await api.getDatasetFeaturesGeoJSON(layer.dataset_id, 'canonical')
          if (!isMounted) return

          // Add or update source
          const existingSource = map.getSource(sourceId) as maplibregl.GeoJSONSource | undefined
          if (existingSource) {
            existingSource.setData(geojsonData as any)
          } else {
            map.addSource(sourceId, {
              type: 'geojson',
              data: geojsonData as any,
            })
          }

          // Add visual layer based on geometry type
          const geomType = layer.geometry_type.toLowerCase()

          if (geomType.includes('polygon')) {
            // Polygon fill
            if (!map.getLayer(fillLayerId)) {
              map.addLayer({
                id: fillLayerId,
                type: 'fill',
                source: sourceId,
                paint: {
                  'fill-color': color,
                  'fill-opacity': 0.35,
                },
              })
            }
            // Polygon boundary line
            if (!map.getLayer(lineLayerId)) {
              map.addLayer({
                id: lineLayerId,
                type: 'line',
                source: sourceId,
                paint: {
                  'line-color': color,
                  'line-width': 2,
                  'line-opacity': 0.9,
                },
              })
            }
          } else if (geomType.includes('point')) {
            // Point circles
            if (!map.getLayer(circleLayerId)) {
              map.addLayer({
                id: circleLayerId,
                type: 'circle',
                source: sourceId,
                paint: {
                  'circle-radius': 6,
                  'circle-color': color,
                  'circle-stroke-width': 1.5,
                  'circle-stroke-color': '#ffffff',
                  'circle-opacity': 0.85,
                },
              })
            }
          } else {
            // LineString / mixed fallback
            if (!map.getLayer(lineLayerId)) {
              map.addLayer({
                id: lineLayerId,
                type: 'line',
                source: sourceId,
                paint: {
                  'line-color': color,
                  'line-width': 2.5,
                  'line-opacity': 0.85,
                },
              })
            }
          }

          // Click handler for feature inspection
          const interactiveLayers = [fillLayerId, lineLayerId, circleLayerId].filter((id) =>
            map.getLayer(id)
          )

          interactiveLayers.forEach((layerId) => {
            map.on('click', layerId, (e: maplibregl.MapLayerMouseEvent) => {
              if (!e.features || e.features.length === 0) return
              const feat = e.features[0]
              const rawProps = feat.properties || {}

              // Extract coordinates summary
              let coordsStr = ''
              if (feat.geometry.type === 'Point') {
                const [x, y] = (feat.geometry as any).coordinates
                coordsStr = `${Number(x).toFixed(5)}, ${Number(y).toFixed(5)}`
              } else {
                coordsStr = `${feat.geometry.type}`
              }

              setSelectedFeature({
                id: String(feat.id || rawProps._source_feature_id || 'N/A'),
                layerName: layer.name,
                geometryType: String(rawProps._geometry_type || layer.geometry_type),
                sourceCrs: String(rawProps._source_crs || layer.source_crs),
                targetCrs: String(rawProps._target_crs || layer.target_crs),
                properties: rawProps,
                coordinatesSummary: coordsStr,
              })
            })

            map.on('mouseenter', layerId, () => {
              map.getCanvas().style.cursor = 'pointer'
            })
            map.on('mouseleave', layerId, () => {
              map.getCanvas().style.cursor = ''
            })
          })

          // Default visibility to true if not set
          setLayerVisibility((prev) => ({
            ...prev,
            [layer.id]: prev[layer.id] !== undefined ? prev[layer.id] : true,
          }))
        }

        // Fit map to combined bounds on initial load if valid bounds exist
        if (combinedBounds) {
          const boundsArr = getBoundsArray(combinedBounds)
          if (boundsArr) {
            map.fitBounds(boundsArr, { padding: 60, maxZoom: 16, duration: 1200 })
          }
        }
      } catch (err) {
        console.error('Failed to load spatial layers into MapLibre:', err)
      } finally {
        if (isMounted) setIsLoadingData(false)
      }
    }

    loadLayersIntoMap()

    return () => {
      isMounted = false
    }
  }, [mapLoaded, layersData])

  // 3. Handle layer visibility toggling
  const toggleLayer = useCallback(
    (layerId: string) => {
      const map = mapRef.current
      if (!map) return

      const newVisibility = !layerVisibility[layerId]
      setLayerVisibility((prev) => ({ ...prev, [layerId]: newVisibility }))

      const visibilityValue = newVisibility ? 'visible' : 'none'
      const possibleLayers = [
        `layer-${layerId}-fill`,
        `layer-${layerId}-line`,
        `layer-${layerId}-circle`,
      ]

      possibleLayers.forEach((id) => {
        if (map.getLayer(id)) {
          map.setLayoutProperty(id, 'visibility', visibilityValue)
        }
      })
    },
    [layerVisibility]
  )

  // 4. Fit map to single layer bounds
  const fitToLayer = (layer: ProjectLayer) => {
    const map = mapRef.current
    if (!map || !layer.bounds) return

    const boundsArr = getBoundsArray(layer.bounds)
    if (boundsArr) {
      map.fitBounds(boundsArr, { padding: 80, maxZoom: 17, duration: 1000 })
    }
  }

  // 5. Fit map to project combined bounds
  const fitToProject = () => {
    const map = mapRef.current
    if (!map || !combinedBounds) return

    const boundsArr = getBoundsArray(combinedBounds)
    if (boundsArr) {
      map.fitBounds(boundsArr, { padding: 80, maxZoom: 16, duration: 1000 })
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
    <div className="relative w-full h-[680px] rounded-xl overflow-hidden border border-border bg-surface-950 flex flex-col font-mono select-none">
      {/* Top Map Toolbar */}
      <div className="h-11 bg-surface-900/90 backdrop-blur border-b border-border px-4 flex items-center justify-between z-10 text-xs">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-slate-200 font-semibold">
            <Layers className="w-4 h-4 text-cyan-400" />
            <span>Map Workspace</span>
          </div>
          <span className="text-slate-500">|</span>
          <div className="text-slate-400 flex items-center gap-1.5">
            <Compass className="w-3.5 h-3.5 text-slate-400" />
            <span>Target CRS:</span>
            <span className="text-cyan-300 font-bold">{targetCrs}</span>
          </div>
          {isLoadingData && (
            <div className="flex items-center gap-1.5 text-cyan-400 text-[11px] animate-pulse">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>Rendering features...</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          {combinedBounds && (
            <button
              onClick={fitToProject}
              title="Fit Extent to All Datasets"
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-surface-850 hover:bg-surface-800 border border-border text-slate-300 hover:text-cyan-300 transition-colors text-[11px]"
            >
              <Crosshair className="w-3 h-3 text-cyan-400" />
              <span>Fit Project Extent</span>
            </button>
          )}

          <button
            onClick={() => refetchLayers()}
            title="Refresh Layers"
            className="p-1 rounded bg-surface-850 hover:bg-surface-800 border border-border text-slate-400 hover:text-slate-200 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => setIsLayersPanelOpen(!isLayersPanelOpen)}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded border text-[11px] transition-colors ${
              isLayersPanelOpen
                ? 'bg-cyan-950/80 border-cyan-800 text-cyan-300'
                : 'bg-surface-850 border-border text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Layers ({layers.length})</span>
          </button>
        </div>
      </div>

      {/* Main Map Canvas Area */}
      <div className="relative flex-1 w-full h-full overflow-hidden">
        {/* MapLibre DOM Container */}
        <div ref={mapContainerRef} className="absolute inset-0 w-full h-full" />

        {/* Floating Layer Control Panel */}
        {isLayersPanelOpen && (
          <div className="absolute top-3 left-3 w-72 max-h-[560px] bg-surface-900/95 backdrop-blur-md border border-border rounded-lg shadow-2xl z-20 flex flex-col overflow-hidden">
            <div className="px-3 py-2.5 border-b border-border flex items-center justify-between bg-surface-950/60">
              <div className="flex items-center gap-2">
                <Layers className="w-3.5 h-3.5 text-cyan-400" />
                <span className="text-[11px] font-bold tracking-wider uppercase text-slate-200">
                  Dataset Layers
                </span>
                <span className="px-1.5 py-0.2 rounded bg-surface-850 text-cyan-400 text-[10px]">
                  {layers.length}
                </span>
              </div>
              <button
                onClick={() => setIsLayersPanelOpen(false)}
                className="text-slate-400 hover:text-slate-200"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="p-2 space-y-2 overflow-y-auto max-h-[480px]">
              {layersLoading ? (
                <div className="py-8 flex flex-col items-center justify-center gap-2 text-slate-500 text-[11px]">
                  <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
                  <span>Loading layers...</span>
                </div>
              ) : layers.length === 0 ? (
                <div className="p-4 text-center text-slate-400 text-[11px] space-y-2">
                  <p>No active spatial layers found in this project.</p>
                  <p className="text-[10px] text-slate-500">
                    Ingest GeoJSON, Shapefile, or CSV datasets to see them rendered here.
                  </p>
                </div>
              ) : (
                layers.map((layer) => {
                  const isVisible = layerVisibility[layer.id] !== false
                  return (
                    <div
                      key={layer.id}
                      className={`p-2.5 rounded border transition-all ${
                        isVisible
                          ? 'bg-surface-950/80 border-border hover:border-slate-600'
                          : 'bg-surface-950/30 border-border/40 opacity-60'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          {/* Color Swatch */}
                          <span
                            className="w-3 h-3 rounded-full flex-shrink-0 shadow"
                            style={{ backgroundColor: layer.color || '#06b6d4' }}
                          />
                          <span className="font-semibold text-slate-200 text-xs truncate" title={layer.name}>
                            {layer.name}
                          </span>
                        </div>

                        <div className="flex items-center gap-1 flex-shrink-0">
                          {layer.bounds && (
                            <button
                              onClick={() => fitToLayer(layer)}
                              title="Zoom to layer extent"
                              className="p-1 rounded hover:bg-surface-800 text-slate-400 hover:text-cyan-300"
                            >
                              <Maximize2 className="w-3 h-3" />
                            </button>
                          )}
                          <button
                            onClick={() => toggleLayer(layer.id)}
                            title={isVisible ? 'Hide layer' : 'Show layer'}
                            className="p-1 rounded hover:bg-surface-800 text-slate-400 hover:text-slate-200"
                          >
                            {isVisible ? (
                              <Eye className="w-3.5 h-3.5 text-cyan-400" />
                            ) : (
                              <EyeOff className="w-3.5 h-3.5 text-slate-500" />
                            )}
                          </button>
                        </div>
                      </div>

                      {/* Layer Metadata Chips */}
                      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[10px]">
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-surface-900 text-slate-300 border border-border">
                          {getFormatIcon(layer.source_format)}
                          <span className="uppercase">{layer.source_format}</span>
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-cyan-950/50 text-cyan-300 border border-cyan-800/60">
                          {layer.geometry_type}
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-surface-900 text-slate-400 border border-border">
                          {layer.feature_count.toLocaleString()} feats
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-slate-900 text-slate-400 border border-border truncate max-w-[120px]" title={layer.source_crs}>
                          {layer.source_crs}
                        </span>
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </div>
        )}

        {/* Selected Feature Inspector Panel */}
        {selectedFeature && (
          <div className="absolute bottom-4 right-4 w-80 max-h-[450px] bg-surface-900/95 backdrop-blur-md border border-cyan-800/80 rounded-lg shadow-2xl z-20 flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Inspector Header */}
            <div className="px-3 py-2 border-b border-border bg-surface-950/80 flex items-center justify-between">
              <div className="flex items-center gap-2 text-cyan-400">
                <Info className="w-3.5 h-3.5" />
                <span className="text-[11px] font-bold uppercase tracking-wider">
                  Feature Inspector
                </span>
              </div>
              <button
                onClick={() => setSelectedFeature(null)}
                className="text-slate-400 hover:text-slate-200 p-0.5"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Inspector Details */}
            <div className="p-3 space-y-3 overflow-y-auto text-xs font-mono">
              <div className="grid grid-cols-2 gap-2 text-[11px] bg-surface-950/60 p-2 rounded border border-border">
                <div>
                  <span className="text-slate-500 block text-[9px] uppercase">Layer</span>
                  <span className="text-slate-200 font-semibold truncate block">{selectedFeature.layerName}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[9px] uppercase">Geometry</span>
                  <span className="text-cyan-300 block">{selectedFeature.geometryType}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[9px] uppercase">Source CRS</span>
                  <span className="text-slate-300 block truncate">{selectedFeature.sourceCrs}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[9px] uppercase">Canonical CRS</span>
                  <span className="text-emerald-400 block truncate">{selectedFeature.targetCrs}</span>
                </div>
              </div>

              {/* Properties Key-Value Table */}
              <div>
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1.5">
                  Canonical Properties
                </span>
                <div className="bg-surface-950/80 rounded border border-border divide-y divide-border/60 max-h-48 overflow-y-auto">
                  {Object.entries(selectedFeature.properties).map(([key, value]) => {
                    if (key.startsWith('_')) return null // Filter internal metadata keys
                    return (
                      <div key={key} className="px-2.5 py-1.5 flex items-start justify-between gap-3 text-[11px]">
                        <span className="text-slate-400 font-medium truncate max-w-[100px]">{key}</span>
                        <span className="text-slate-200 text-right truncate max-w-[140px]" title={String(value)}>
                          {value === null || value === undefined ? (
                            <span className="text-slate-600 italic">null</span>
                          ) : (
                            String(value)
                          )}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Bottom Map Status Bar */}
      <div className="h-7 bg-surface-950 border-t border-border px-4 flex items-center justify-between text-[11px] text-slate-400 z-10">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1">
            <span className="text-slate-500">CURSOR:</span>
            {cursorCoords ? (
              <span className="text-slate-300">
                {cursorCoords.lon.toFixed(4)}°, {cursorCoords.lat.toFixed(4)}°
              </span>
            ) : (
              <span className="text-slate-600">--</span>
            )}
          </div>
          <span className="text-slate-600">|</span>
          <div className="flex items-center gap-1">
            <span className="text-slate-500">ZOOM:</span>
            <span className="text-slate-300">{currentZoom}</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-emerald-400 text-[10px]">Interactive PostGIS Vector Engine</span>
          </div>
        </div>
      </div>
    </div>
  )
}
