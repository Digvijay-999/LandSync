import React, { useEffect, useRef, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
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
  Sparkles,
  ShieldCheck,
  AlertTriangle,
} from 'lucide-react'
import { useProjectLayers } from '../../hooks/useDatasets'
import { api } from '../../services/api'
import { useAppStore } from '../../stores/useAppStore'
import { SpatialAnalysisPanel } from '../analysis/SpatialAnalysisPanel'
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

  const {
    activeSpatialAnalysis,
    clearActiveSpatialAnalysis,
    analysisPanelOpen,
    setAnalysisPanelOpen,
    toggleAnalysisPanel,
    openAssistantWithRecord,
  } = useAppStore()

  // Stage 12 Unified Land Records Layer State
  const [unifiedLayerVisible, setUnifiedLayerVisible] = useState(true)
  const [loadingUnified, setLoadingUnified] = useState(false)
  const [unifiedStats, setUnifiedStats] = useState<{
    total: number
    authoritative: number
    quarantined: number
  } | null>(null)
  const [unifiedBounds, setUnifiedBounds] = useState<[[number, number], [number, number]] | null>(null)
  const [unifiedRefreshKey, setUnifiedRefreshKey] = useState(0)

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

  // Extract bbox from GeoJSON FeatureCollection
  const computeBboxFromGeoJSON = (geojson: any): [[number, number], [number, number]] | null => {
    if (!geojson || !geojson.features || geojson.features.length === 0) return null
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    const extract = (c: any) => {
      if (typeof c[0] === 'number' && typeof c[1] === 'number') {
        minX = Math.min(minX, c[0])
        minY = Math.min(minY, c[1])
        maxX = Math.max(maxX, c[0])
        maxY = Math.max(maxY, c[1])
      } else if (Array.isArray(c)) {
        c.forEach(extract)
      }
    }
    for (const f of geojson.features) {
      if (f.geometry?.coordinates) extract(f.geometry.coordinates)
    }
    if (isFinite(minX) && isFinite(minY) && isFinite(maxX) && isFinite(maxY) && (minX !== maxX || minY !== maxY)) {
      return [
        [minX, minY],
        [maxX, maxY],
      ]
    }
    return null
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

  // Sync Spatial Analysis Result Layer on MapLibre
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapLoaded) return

    const sourceId = 'spatial-analysis-source'
    const fillLayerId = 'layer-analysis-fill'
    const lineLayerId = 'layer-analysis-line'
    const circleLayerId = 'layer-analysis-circle'

    if (!activeSpatialAnalysis || !activeSpatialAnalysis.result_geojson) {
      if (map.getLayer(fillLayerId)) map.removeLayer(fillLayerId)
      if (map.getLayer(lineLayerId)) map.removeLayer(lineLayerId)
      if (map.getLayer(circleLayerId)) map.removeLayer(circleLayerId)
      if (map.getSource(sourceId)) map.removeSource(sourceId)
      return
    }

    const geojson = activeSpatialAnalysis.result_geojson

    if (map.getSource(sourceId)) {
      ;(map.getSource(sourceId) as maplibregl.GeoJSONSource).setData(geojson as any)
    } else {
      map.addSource(sourceId, {
        type: 'geojson',
        data: geojson as any,
      })

      map.addLayer({
        id: fillLayerId,
        type: 'fill',
        source: sourceId,
        paint: {
          'fill-color': [
            'match',
            ['get', '_role'],
            'overlap_intersection', '#f59e0b',
            'analysis_buffer', '#6366f1',
            'conflict_zone', '#f43f5e',
            'comparison_overlap', '#eab308',
            'comparison_a_only', '#06b6d4',
            'comparison_b_only', '#10b981',
            'version_added', '#10b981',
            'version_removed', '#f43f5e',
            'version_changed', '#f59e0b',
            'version_unchanged', '#64748b',
            'proximity_match', '#06b6d4',
            'proximity_reference', '#818cf8',
            '#06b6d4'
          ],
          'fill-opacity': 0.35,
        },
      })

      map.addLayer({
        id: lineLayerId,
        type: 'line',
        source: sourceId,
        paint: {
          'line-color': [
            'match',
            ['get', '_role'],
            'overlap_intersection', '#fbbf24',
            'analysis_buffer', '#818cf8',
            'conflict_zone', '#fb7185',
            'version_added', '#34d399',
            'version_removed', '#fb7185',
            'version_changed', '#fbbf24',
            'version_unchanged', '#94a3b8',
            'proximity_match', '#22d3ee',
            'proximity_reference', '#a5b4fc',
            '#22d3ee'
          ],
          'line-width': 2.5,
          'line-opacity': 0.95,
        },
      })

      map.addLayer({
        id: circleLayerId,
        type: 'circle',
        source: sourceId,
        filter: ['in', ['geometry-type'], ['literal', ['Point', 'MultiPoint']]],
        paint: {
          'circle-radius': [
            'match',
            ['get', '_role'],
            'conflict_hotspot', 10,
            'search_target', 8,
            'version_added', 8,
            'version_removed', 8,
            'version_changed', 8,
            'proximity_reference', 9,
            'proximity_match', 7,
            6
          ],
          'circle-color': [
            'match',
            ['get', '_role'],
            'conflict_hotspot', '#ef4444',
            'search_target', '#eab308',
            'version_added', '#10b981',
            'version_removed', '#f43f5e',
            'version_changed', '#f59e0b',
            'version_unchanged', '#64748b',
            'proximity_reference', '#818cf8',
            'proximity_match', '#06b6d4',
            '#06b6d4'
          ],
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff',
          'circle-opacity': 0.95,
        },
      })

      ;[fillLayerId, lineLayerId, circleLayerId].forEach((lid) => {
        map.on('click', lid, (e: maplibregl.MapLayerMouseEvent) => {
          if (!e.features || e.features.length === 0) return
          const feat = e.features[0]
          setSelectedFeature({
            id: String(feat.id || feat.properties?.id || feat.properties?.identifier || 'Analysis Feature'),
            layerName: activeSpatialAnalysis.title,
            geometryType: String(feat.geometry.type),
            sourceCrs: 'EPSG:4326',
            targetCrs: targetCrs,
            properties: feat.properties || {},
            coordinatesSummary: `${feat.geometry.type} Spatial Result`,
          })
        })

        map.on('mouseenter', lid, () => {
          map.getCanvas().style.cursor = 'pointer'
        })
        map.on('mouseleave', lid, () => {
          map.getCanvas().style.cursor = ''
        })
      })
    }

    // Auto-fit to analysis result extent
    const features = geojson.features || []
    if (features.length > 0) {
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
      features.forEach((f: any) => {
        const coords = f.geometry?.coordinates
        const extractPoints = (c: any) => {
          if (typeof c[0] === 'number') {
            minX = Math.min(minX, c[0])
            maxX = Math.max(maxX, c[0])
            minY = Math.min(minY, c[1])
            maxY = Math.max(maxY, c[1])
          } else if (Array.isArray(c)) {
            c.forEach(extractPoints)
          }
        }
        if (coords) extractPoints(coords)
      })

      if (isFinite(minX) && isFinite(minY) && isFinite(maxX) && isFinite(maxY) && (minX !== maxX || minY !== maxY)) {
        map.fitBounds(
          [
            [minX, minY],
            [maxX, maxY],
          ],
          { padding: 80, maxZoom: 16, duration: 1000 }
        )
      }
    }
  }, [mapLoaded, activeSpatialAnalysis, targetCrs])

  // Load Stage 12 Unified Land Records into MapLibre
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapLoaded || !projectId) return

    let isMounted = true

    const loadUnifiedRecords = async () => {
      setLoadingUnified(true)
      try {
        // Fetch project unified records GeoJSON via existing Stage 12 export endpoint
        const blob = await api.exportProjectGeoJSON(projectId)
        const text = await blob.text()
        const parsed = JSON.parse(text)
        if (!isMounted) return

        let authoritativeCount = 0
        let quarantinedCount = 0

        // Enrich features with geometry for quarantined records from contributing sources
        const enrichedFeatures = await Promise.all(
          (parsed.features || []).map(async (feat: any) => {
            const props = feat.properties || {}
            const isQuarantined =
              props.status === 'CONFLICT' || props.resolution_status === 'REJECTED'

            if (isQuarantined) {
              quarantinedCount++
            } else {
              authoritativeCount++
            }

            // If feature canonical_geometry is null (quarantined records), load contributing source footprint
            if (!feat.geometry && props.id) {
              try {
                const detail = await api.getUnifiedRecordDetail(props.id)
                const validSource = detail.sources?.find((s) => s.geometry)
                if (validSource && validSource.geometry) {
                  return {
                    ...feat,
                    geometry: validSource.geometry,
                    properties: {
                      ...props,
                      _is_quarantined_footprint: true,
                      _source_role: validSource.source_role,
                    },
                  }
                }
              } catch (e) {
                // Ignore fallback error
              }
            }
            return feat
          })
        )

        if (!isMounted) return

        const enrichedGeoJSON = {
          type: 'FeatureCollection',
          features: enrichedFeatures,
        }

        const total = enrichedFeatures.length
        setUnifiedStats({
          total,
          authoritative: authoritativeCount,
          quarantined: quarantinedCount,
        })

        const bounds = computeBboxFromGeoJSON(enrichedGeoJSON)
        setUnifiedBounds(bounds)

        const sourceId = 'src-unified-records'
        const fillAuthId = 'layer-unified-authoritative-fill'
        const lineAuthId = 'layer-unified-authoritative-line'
        const fillQuarId = 'layer-unified-quarantined-fill'
        const lineQuarId = 'layer-unified-quarantined-line'

        // 1. Add or update source
        const existingSource = map.getSource(sourceId) as maplibregl.GeoJSONSource | undefined
        if (existingSource) {
          existingSource.setData(enrichedGeoJSON as any)
        } else {
          map.addSource(sourceId, {
            type: 'geojson',
            data: enrichedGeoJSON as any,
          })
        }

        // 2. Authoritative Fill Layer (Emerald)
        if (!map.getLayer(fillAuthId)) {
          map.addLayer({
            id: fillAuthId,
            type: 'fill',
            source: sourceId,
            filter: ['!=', ['get', 'status'], 'CONFLICT'],
            paint: {
              'fill-color': '#10b981',
              'fill-opacity': 0.4,
            },
          })
        }

        // 3. Authoritative Line Layer (Solid Emerald)
        if (!map.getLayer(lineAuthId)) {
          map.addLayer({
            id: lineAuthId,
            type: 'line',
            source: sourceId,
            filter: ['!=', ['get', 'status'], 'CONFLICT'],
            paint: {
              'line-color': '#34d399',
              'line-width': 3,
              'line-opacity': 0.95,
            },
          })
        }

        // 4. Quarantined Fill Layer (Rose Tint)
        if (!map.getLayer(fillQuarId)) {
          map.addLayer({
            id: fillQuarId,
            type: 'fill',
            source: sourceId,
            filter: ['==', ['get', 'status'], 'CONFLICT'],
            paint: {
              'fill-color': '#f43f5e',
              'fill-opacity': 0.35,
            },
          })
        }

        // 5. Quarantined Line Layer (Dashed Rose)
        if (!map.getLayer(lineQuarId)) {
          map.addLayer({
            id: lineQuarId,
            type: 'line',
            source: sourceId,
            filter: ['==', ['get', 'status'], 'CONFLICT'],
            paint: {
              'line-color': '#fb7185',
              'line-width': 2.5,
              'line-opacity': 0.95,
              'line-dasharray': [3, 2],
            },
          })
        }

        // Apply initial visibility
        const vis = unifiedLayerVisible ? 'visible' : 'none'
        ;[fillAuthId, lineAuthId, fillQuarId, lineQuarId].forEach((lid) => {
          if (map.getLayer(lid)) {
            map.setLayoutProperty(lid, 'visibility', vis)
          }
        })

        // 6. Interactive Clicks on Unified Layers
        const unifiedLayerIds = [fillAuthId, lineAuthId, fillQuarId, lineQuarId]
        unifiedLayerIds.forEach((layerId) => {
          map.on('click', layerId, (e: maplibregl.MapLayerMouseEvent) => {
            if (!e.features || e.features.length === 0) return
            const feat = e.features[0]
            const rawProps = feat.properties || {}
            const isQuarantined =
              rawProps.status === 'CONFLICT' || rawProps.resolution_status === 'REJECTED'

            let coordsStr = ''
            if (feat.geometry.type === 'Point') {
              const [x, y] = (feat.geometry as any).coordinates
              coordsStr = `${Number(x).toFixed(5)}, ${Number(y).toFixed(5)}`
            } else {
              coordsStr = `${feat.geometry.type} (${
                isQuarantined ? 'Quarantined Footprint' : 'Authoritative Master'
              })`
            }

            setSelectedFeature({
              id: String(rawProps.record_identifier || feat.id || 'Unified Record'),
              layerName: isQuarantined
                ? 'Unified Records (Stage 12 Quarantined)'
                : 'Unified Records (Stage 12 Authoritative)',
              geometryType: String(feat.geometry.type),
              sourceCrs: 'EPSG:4326',
              targetCrs: targetCrs,
              properties: {
                record_identifier: rawProps.record_identifier,
                status: isQuarantined ? 'QUARANTINED (CONFLICT)' : 'AUTHORITATIVE (ACTIVE)',
                resolution_status: rawProps.resolution_status || (isQuarantined ? 'REJECTED' : 'UNIFIED'),
                area_sqm: rawProps.area_sqm
                  ? `${Number(rawProps.area_sqm).toLocaleString()} m²`
                  : 'N/A',
                land_use: rawProps.land_use || 'Not Specified',
                conflict_status:
                  rawProps.conflict_status || (isQuarantined ? 'UNRESOLVED_CONFLICTS' : 'NO_CONFLICTS'),
                conflict_count: rawProps.conflict_count ?? (isQuarantined ? 1 : 0),
                source_count: rawProps.source_count ?? 2,
                source_datasets: Array.isArray(rawProps.source_datasets)
                  ? rawProps.source_datasets.join(', ')
                  : String(rawProps.source_datasets || 'N/A'),
                source_feature_identifiers: Array.isArray(rawProps.source_feature_identifiers)
                  ? rawProps.source_feature_identifiers.join(', ')
                  : String(rawProps.source_feature_identifiers || 'N/A'),
                geometry_source_role: rawProps.geometry_source_role || 'CADASTRAL',
                _is_unified_record: true,
                _unified_record_id: rawProps.id,
              },
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
      } catch (err) {
        console.warn('No Stage 12 unified records found for this project yet or error loading:', err)
      } finally {
        if (isMounted) setLoadingUnified(false)
      }
    }

    loadUnifiedRecords()

    return () => {
      isMounted = false
    }
  }, [mapLoaded, projectId, targetCrs, unifiedRefreshKey])

  // Handle unified records layer visibility toggle
  const toggleUnifiedLayer = useCallback(() => {
    const map = mapRef.current
    if (!map) return

    const newVisibility = !unifiedLayerVisible
    setUnifiedLayerVisible(newVisibility)

    const visibilityValue = newVisibility ? 'visible' : 'none'
    const unifiedLayers = [
      'layer-unified-authoritative-fill',
      'layer-unified-authoritative-line',
      'layer-unified-quarantined-fill',
      'layer-unified-quarantined-line',
    ]

    unifiedLayers.forEach((id) => {
      if (map.getLayer(id)) {
        map.setLayoutProperty(id, 'visibility', visibilityValue)
      }
    })
  }, [unifiedLayerVisible])

  // Fit map to unified records extent
  const fitToUnifiedExtent = useCallback(() => {
    const map = mapRef.current
    if (!map || !unifiedBounds) return
    map.fitBounds(unifiedBounds, { padding: 80, maxZoom: 17, duration: 1000 })
  }, [unifiedBounds])

  // Combined refresh handler
  const handleRefreshAll = () => {
    refetchLayers()
    setUnifiedRefreshKey((k) => k + 1)
  }

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
            onClick={handleRefreshAll}
            title="Refresh All Spatial Layers & Unified Records"
            className="p-1 rounded bg-surface-850 hover:bg-surface-800 border border-border text-slate-400 hover:text-slate-200 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loadingUnified ? 'animate-spin text-cyan-400' : ''}`} />
          </button>

          {unifiedStats && unifiedStats.total > 0 && (
            <button
              onClick={toggleUnifiedLayer}
              title={unifiedLayerVisible ? 'Hide Stage 12 Unified Land Records Overlay' : 'Show Stage 12 Unified Land Records Overlay'}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded border text-[11px] transition-colors ${
                unifiedLayerVisible
                  ? 'bg-emerald-950/80 border-emerald-800 text-emerald-300 font-bold shadow-sm'
                  : 'bg-surface-850 border-border text-slate-400 hover:text-slate-200'
              }`}
            >
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              <span>Unified Records ({unifiedStats.total})</span>
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  unifiedLayerVisible ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50' : 'bg-slate-600'
                }`}
              />
            </button>
          )}

          <button
            onClick={() => toggleAnalysisPanel()}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded border text-[11px] transition-colors ${
              analysisPanelOpen
                ? 'bg-cyan-950/80 border-cyan-800 text-cyan-300 font-bold'
                : 'bg-surface-850 border-border text-slate-400 hover:text-slate-200'
            }`}
          >
            <Compass className="w-3.5 h-3.5 text-cyan-400" />
            <span>Spatial Analysis</span>
            {activeSpatialAnalysis && (
              <span className="w-2 h-2 rounded-full bg-cyan-400" />
            )}
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
            <span>Layers ({layers.length + (unifiedStats && unifiedStats.total > 0 ? 1 : 0)})</span>
          </button>
        </div>
      </div>

      {/* Main Map Canvas Area */}
      <div className="relative flex-1 w-full h-full overflow-hidden">
        {/* MapLibre DOM Container */}
        <div ref={mapContainerRef} className="absolute inset-0 w-full h-full" />

        {/* Floating Active Spatial Analysis Status Banner */}
        {activeSpatialAnalysis && (
          <div className="absolute top-3 left-1/2 -translate-x-1/2 bg-surface-900/95 backdrop-blur-md border border-cyan-600/80 rounded-full px-4 py-1.5 shadow-2xl flex items-center gap-3 z-20 text-xs">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            <span className="font-bold text-cyan-300 truncate max-w-xs">{activeSpatialAnalysis.title}</span>
            <span className="px-2 py-0.5 rounded-full bg-cyan-950 border border-cyan-800 text-[10px] text-cyan-300 font-bold">
              {activeSpatialAnalysis.result_count} items
            </span>
            <button
              onClick={() => clearActiveSpatialAnalysis()}
              className="p-0.5 rounded-full text-slate-400 hover:text-rose-400 transition-colors"
              title="Clear analysis overlay"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Floating Spatial Analysis Panel Drawer */}
        {analysisPanelOpen && (
          <div className="absolute top-3 right-3 w-96 max-h-[640px] z-30 shadow-2xl">
            <SpatialAnalysisPanel
              projectId={projectId}
              onClose={() => setAnalysisPanelOpen(false)}
            />
          </div>
        )}

        {/* Floating Layer Control Panel */}
        {isLayersPanelOpen && (
          <div className="absolute top-3 left-3 w-72 max-h-[560px] bg-surface-900/95 backdrop-blur-md border border-border rounded-lg shadow-2xl z-20 flex flex-col overflow-hidden">
            <div className="px-3 py-2.5 border-b border-border flex items-center justify-between bg-surface-950/60">
              <div className="flex items-center gap-2">
                <Layers className="w-3.5 h-3.5 text-cyan-400" />
                <span className="text-[11px] font-bold tracking-wider uppercase text-slate-200">
                  Map Layers
                </span>
                <span className="px-1.5 py-0.2 rounded bg-surface-850 text-cyan-400 text-[10px]">
                  {layers.length + (unifiedStats && unifiedStats.total > 0 ? 1 : 0)}
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
              {/* Stage 12 Unified Land Records Layer Card */}
              {loadingUnified ? (
                <div className="p-2.5 rounded border border-emerald-900/50 bg-emerald-950/20 flex items-center gap-2 text-slate-400 text-[11px]">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-400" />
                  <span>Loading Stage 12 unified records...</span>
                </div>
              ) : unifiedStats && unifiedStats.total > 0 ? (
                <div
                  className={`p-2.5 rounded-lg border transition-all ${
                    unifiedLayerVisible
                      ? 'bg-surface-950/90 border-emerald-700/80 shadow-md ring-1 ring-emerald-500/20'
                      : 'bg-surface-950/40 border-border/40 opacity-60'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="w-3.5 h-3.5 rounded bg-emerald-500/20 border border-emerald-400 flex items-center justify-center flex-shrink-0">
                        <ShieldCheck className="w-2.5 h-2.5 text-emerald-400" />
                      </span>
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-slate-100 text-xs truncate">
                            Unified Records
                          </span>
                          <span className="px-1.5 py-0.2 rounded bg-emerald-950 border border-emerald-800 text-emerald-300 text-[9px] font-bold tracking-wider uppercase">
                            Stage 12
                          </span>
                        </div>
                        <p className="text-[10px] text-slate-400 truncate">
                          Master Synthesized Cadastre
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-1 flex-shrink-0">
                      {unifiedBounds && (
                        <button
                          onClick={fitToUnifiedExtent}
                          title="Zoom to unified records extent"
                          className="p-1 rounded hover:bg-surface-800 text-slate-400 hover:text-emerald-300 transition-colors"
                        >
                          <Maximize2 className="w-3 h-3" />
                        </button>
                      )}
                      <button
                        onClick={toggleUnifiedLayer}
                        title={unifiedLayerVisible ? 'Hide unified records layer' : 'Show unified records layer'}
                        className="p-1 rounded hover:bg-surface-800 text-slate-400 hover:text-slate-200 transition-colors"
                      >
                        {unifiedLayerVisible ? (
                          <Eye className="w-3.5 h-3.5 text-emerald-400" />
                        ) : (
                          <EyeOff className="w-3.5 h-3.5 text-slate-500" />
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Legend / Status breakdown */}
                  <div className="mt-2 pt-2 border-t border-border/60 flex items-center justify-between text-[10px]">
                    <div className="flex items-center gap-1.5" title="Authoritative reconciled parcels with valid geometry">
                      <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500/80 border border-emerald-300 flex-shrink-0" />
                      <span className="text-slate-300">
                        Authoritative: <strong className="text-emerald-400 font-bold">{unifiedStats.authoritative}</strong>
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5" title="Quarantined parcels requiring resolution or disputed">
                      <span className="w-2.5 h-2.5 rounded-sm bg-rose-500/70 border border-rose-400 border-dashed flex-shrink-0" />
                      <span className="text-slate-300">
                        Quarantined: <strong className="text-rose-400 font-bold">{unifiedStats.quarantined}</strong>
                      </span>
                    </div>
                  </div>
                </div>
              ) : null}

              {/* Source Dataset Layers Section Header */}
              {layers.length > 0 && (
                <div className="pt-1 pb-0.5 flex items-center justify-between text-[10px] text-slate-400 uppercase tracking-wider font-semibold">
                  <span>Source Datasets ({layers.length})</span>
                </div>
              )}

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
              {/* Unified Record Status Banner */}
              {selectedFeature.properties._is_unified_record && (
                <div className="rounded border overflow-hidden">
                  {selectedFeature.properties.status?.includes('AUTHORITATIVE') ? (
                    <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-emerald-950/90 border-emerald-700/80 text-emerald-300 font-bold text-[11px]">
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                      <span>Authoritative Unified Land Record</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-rose-950/90 border-rose-700/80 text-rose-300 font-bold text-[11px]">
                      <AlertTriangle className="w-3.5 h-3.5 text-rose-400 flex-shrink-0" />
                      <span>Quarantined Land Record (Under Review)</span>
                    </div>
                  )}
                </div>
              )}

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

              {/* Quick Actions for Unified Records */}
              {selectedFeature.properties._is_unified_record && (
                <div className="pt-2 border-t border-border flex items-center gap-2">
                  <button
                    onClick={() => {
                      if (selectedFeature.properties._unified_record_id) {
                        openAssistantWithRecord(selectedFeature.properties._unified_record_id)
                      }
                    }}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 px-2 py-1.5 rounded bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-800 text-[10px] text-cyan-300 font-bold transition-colors shadow-sm"
                    title="Ask AI Copilot about this record"
                  >
                    <Sparkles className="w-3 h-3 text-cyan-400" />
                    <span>Ask Copilot</span>
                  </button>
                  <Link
                    to={`/projects/${projectId}/unified-records`}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 px-2 py-1.5 rounded bg-surface-850 hover:bg-surface-800 border border-border text-[10px] text-slate-200 hover:text-white transition-colors"
                    title="Open Stage 12 Unified Records Table"
                  >
                    <ShieldCheck className="w-3 h-3 text-emerald-400" />
                    <span>Stage 12 Table</span>
                  </Link>
                </div>
              )}
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
