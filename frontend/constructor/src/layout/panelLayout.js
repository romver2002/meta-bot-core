export const DESKTOP_BREAKPOINT = 900
export const MIN_CANVAS_WIDTH = 360
export const RAIL_RESIZER_WIDTH = 10
export const PANEL_LAYOUT_STORAGE_KEY = 'meta-bot-core.constructor.panel-layout.v1'

export const PANEL_LIMITS = Object.freeze({
  palette: Object.freeze({ min: 220, max: 480, default: 256 }),
  inspector: Object.freeze({ min: 300, max: 640, default: 400 }),
  json: Object.freeze({ min: 320, max: 720, default: 420 }),
})

const panelNames = Object.keys(PANEL_LIMITS)

function configFor(panel) {
  const config = PANEL_LIMITS[panel]
  if (!config) throw new RangeError(`Unknown panel: ${panel}`)
  return config
}

function finiteNumber(value) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

export function isDesktopViewport(viewportWidth) {
  return finiteNumber(viewportWidth) > DESKTOP_BREAKPOINT
}

export function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
}

export function clampPanelWidth(panel, width) {
  const config = configFor(panel)
  const numeric = finiteNumber(width)
  if (numeric === null) return config.default
  return Math.round(clamp(numeric, config.min, config.max))
}

export function defaultPanelWidths() {
  return Object.fromEntries(panelNames.map((panel) => [panel, PANEL_LIMITS[panel].default]))
}

export function normalizePanelWidths(widths) {
  const source = widths && typeof widths === 'object' ? widths : {}
  return Object.fromEntries(panelNames.map((panel) => [panel, clampPanelWidth(panel, source[panel])]))
}

export function maxRailWidth(panel, { viewportWidth, oppositeOpen = false, oppositeWidth = 0 } = {}) {
  if (panel !== 'palette' && panel !== 'inspector') {
    throw new RangeError(`Rail panel expected, received: ${panel}`)
  }

  const config = configFor(panel)
  const viewport = finiteNumber(viewportWidth)
  if (viewport === null) return config.max

  const otherWidth = oppositeOpen ? Math.max(0, finiteNumber(oppositeWidth) || 0) : 0
  const resizers = oppositeOpen ? RAIL_RESIZER_WIDTH * 2 : RAIL_RESIZER_WIDTH
  const available = Math.floor(viewport - MIN_CANVAS_WIDTH - resizers - otherWidth)
  return Math.max(config.min, Math.min(config.max, available))
}

export function clampRailWidth(panel, width, options) {
  const config = configFor(panel)
  const max = maxRailWidth(panel, options)
  return Math.round(clamp(clampPanelWidth(panel, width), config.min, max))
}

export function maxJsonDrawerWidth(viewportWidth) {
  const config = configFor('json')
  const viewport = finiteNumber(viewportWidth)
  if (viewport === null) return config.max
  return Math.max(config.min, Math.min(config.max, Math.floor(viewport - 64)))
}

export function clampJsonDrawerWidth(width, viewportWidth) {
  const config = configFor('json')
  return Math.round(clamp(clampPanelWidth('json', width), config.min, maxJsonDrawerWidth(viewportWidth)))
}

export function loadPanelWidths(storage) {
  try {
    const raw = storage?.getItem(PANEL_LAYOUT_STORAGE_KEY)
    if (!raw) return defaultPanelWidths()
    return normalizePanelWidths(JSON.parse(raw))
  } catch {
    return defaultPanelWidths()
  }
}

export function savePanelWidths(storage, widths) {
  try {
    if (!storage) return false
    storage.setItem(PANEL_LAYOUT_STORAGE_KEY, JSON.stringify(normalizePanelWidths(widths)))
    return true
  } catch {
    return false
  }
}
