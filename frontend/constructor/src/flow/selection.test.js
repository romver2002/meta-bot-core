import assert from 'node:assert/strict'
import test from 'node:test'

import { buttonHandleId } from './handles.js'
import { createBlockSelectionSnapshot, pasteBlockSelectionSnapshot } from './selection.js'

const menu = {
  id: 'menu',
  selected: true,
  position: { x: 100, y: 100 },
  data: {
    group: 'block',
    type: 'show_buttons',
    params: { buttons: [{ label: 'Далее', action: 'next', target: 'done' }] },
  },
}

const done = {
  id: 'done',
  selected: true,
  position: { x: 340, y: 100 },
  data: { group: 'block', type: 'send_message', params: { text: 'Готово' } },
}

const external = {
  id: 'external',
  selected: false,
  position: { x: 600, y: 100 },
  data: { group: 'block', type: 'send_message', params: { text: 'Внешний блок' } },
}

const callbackMenu = {
  id: 'callback-menu',
  selected: true,
  position: { x: 100, y: 280 },
  data: {
    group: 'block',
    type: 'show_buttons',
    params: { buttons: [{ label: 'Позвать', action: 'callback', target: 'call_specialist' }] },
  },
}

test('copies selected blocks with remapped internal button targets and internal edges only', () => {
  const nodes = [menu, done, external]
  const edges = [
    { id: 'menu-done', source: 'menu', sourceHandle: buttonHandleId(0), target: 'done', data: { bend: { x: 24, y: 8 } } },
    { id: 'done-external', source: 'done', sourceHandle: 'next', target: 'external' },
    { id: 'external-done', source: 'external', sourceHandle: 'next', target: 'done' },
  ]
  const snapshot = createBlockSelectionSnapshot(nodes, edges)
  let nodeNumber = 0
  let edgeNumber = 0

  const result = pasteBlockSelectionSnapshot({
    nodes,
    edges,
    snapshot,
    createNodeId: () => `copy-${++nodeNumber}`,
    createEdgeId: () => `edge-copy-${++edgeNumber}`,
  })

  const copiedMenu = result.nodes.find((node) => node.id === 'copy-1')
  const copiedDone = result.nodes.find((node) => node.id === 'copy-2')
  assert.equal(copiedMenu.data.params.buttons[0].target, copiedDone.id)
  assert.deepEqual(copiedMenu.position, { x: 148, y: 148 })
  assert.equal(result.edges.some((edge) => edge.source === copiedMenu.id && edge.target === copiedDone.id), true)
  assert.equal(result.edges.some((edge) => edge.source === copiedDone.id && edge.target === 'external'), false)
  assert.equal(result.edges.some((edge) => edge.source === 'external' && edge.target === copiedDone.id), false)
  assert.equal(result.edges.find((edge) => edge.source === copiedMenu.id).data.bend, undefined)
  assert.equal(result.nodes.filter((node) => node.id === 'menu' || node.id === 'done').every((node) => !node.selected), true)
})

test('keeps a non-transition button target as its literal payload', () => {
  const snapshot = createBlockSelectionSnapshot([callbackMenu], [])
  const result = pasteBlockSelectionSnapshot({
    nodes: [callbackMenu],
    edges: [],
    snapshot,
    createNodeId: () => 'callback-copy',
    createEdgeId: () => 'unused',
  })

  assert.equal(result.nodes.find((node) => node.id === 'callback-copy').data.params.buttons[0].target, 'call_specialist')
})

test('clears an external next target instead of linking a copied block to the original graph', () => {
  const snapshot = createBlockSelectionSnapshot([menu, { ...done, selected: false }], [
    { id: 'menu-done', source: 'menu', sourceHandle: buttonHandleId(0), target: 'done' },
  ])
  const result = pasteBlockSelectionSnapshot({
    nodes: [menu, done],
    edges: [{ id: 'menu-done', source: 'menu', sourceHandle: buttonHandleId(0), target: 'done' }],
    snapshot,
    createNodeId: () => 'menu-copy',
    createEdgeId: () => 'unused',
  })

  assert.equal(result.nodes.find((node) => node.id === 'menu-copy').data.params.buttons[0].target, '')
  assert.equal(result.edges.some((edge) => edge.source === 'menu-copy'), false)
})
