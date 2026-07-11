import assert from 'node:assert/strict'
import test from 'node:test'

import {
  PANEL_LAYOUT_STORAGE_KEY,
  clampJsonDrawerWidth,
  clampRailWidth,
  defaultPanelWidths,
  loadPanelWidths,
  maxRailWidth,
  normalizePanelWidths,
  savePanelWidths,
} from './panelLayout.js'

test('normalizes persisted panel widths to their safe limits', () => {
  assert.deepEqual(normalizePanelWidths({ palette: 120, inspector: 900, json: '475.2' }), {
    palette: 220,
    inspector: 640,
    json: 475,
  })
})

test('keeps enough room for the canvas while both rails are open', () => {
  assert.equal(maxRailWidth('palette', {
    viewportWidth: 1000,
    oppositeOpen: true,
    oppositeWidth: 400,
  }), 220)
  assert.equal(clampRailWidth('palette', 480, {
    viewportWidth: 1000,
    oppositeOpen: true,
    oppositeWidth: 400,
  }), 220)
})

test('limits the JSON drawer without allowing it to cover the whole viewport', () => {
  assert.equal(clampJsonDrawerWidth(720, 560), 496)
})

test('uses defaults for malformed saved data and saves normalized values', () => {
  const storage = {
    value: '{bad json',
    getItem(key) { return key === PANEL_LAYOUT_STORAGE_KEY ? this.value : null },
    setItem(key, value) { if (key === PANEL_LAYOUT_STORAGE_KEY) this.value = value },
  }

  assert.deepEqual(loadPanelWidths(storage), defaultPanelWidths())
  assert.equal(savePanelWidths(storage, { palette: 999, inspector: 350, json: 100 }), true)
  assert.deepEqual(JSON.parse(storage.value), { palette: 480, inspector: 350, json: 320 })
})

test('keeps the editor usable when browser storage is unavailable', () => {
  const unavailableStorage = {
    getItem() { throw new Error('storage is blocked') },
    setItem() { throw new Error('storage is blocked') },
  }

  assert.deepEqual(loadPanelWidths(unavailableStorage), defaultPanelWidths())
  assert.equal(savePanelWidths(unavailableStorage, defaultPanelWidths()), false)
  assert.equal(savePanelWidths(undefined, defaultPanelWidths()), false)
})
