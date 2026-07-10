import assert from 'node:assert/strict'
import test from 'node:test'

import { buttonHandleId } from './handles.js'
import { serializeDefinition, validateFlow } from './serialize.js'

const trigger = {
  id: 'start',
  data: { group: 'trigger', type: 'start', config: {} },
}

const message = (id, text = 'Готово') => ({
  id,
  data: { group: 'block', type: 'send_message', params: { text } },
})

const menu = (buttons) => ({
  id: 'menu',
  data: { group: 'block', type: 'show_buttons', params: { text: 'Выберите действие', buttons } },
})

test('serializes a button transition as Button.target, not a Flow transition', () => {
  const nodes = [
    trigger,
    menu([{ label: 'Продолжить', action: 'next', target: 'done' }]),
    message('done'),
  ]
  const edges = [
    { id: 'start-menu', source: 'start', target: 'menu' },
    { id: 'menu-done', source: 'menu', sourceHandle: buttonHandleId(0), target: 'done' },
  ]

  const result = validateFlow(nodes, edges, 'telegram')
  const definition = serializeDefinition(nodes, edges)

  assert.equal(result.ok, true)
  assert.deepEqual(definition.nodes[0].buttons, [{ label: 'Продолжить', action: 'next', target: 'done' }])
  assert.deepEqual(definition.transitions, [])
})

test('rejects a menu button whose target is invisible on the canvas', () => {
  const nodes = [
    trigger,
    menu([{ label: 'Продолжить', action: 'next', target: 'done' }]),
    message('done'),
  ]
  const edges = [{ id: 'start-menu', source: 'start', target: 'menu' }]

  const result = validateFlow(nodes, edges, 'telegram')

  assert.equal(result.ok, false)
  assert.ok(result.problems.some((problem) => problem.nodeId === 'menu' && problem.message.includes('связь на холсте')))
})

test('rejects a show-buttons block without a choice', () => {
  const nodes = [trigger, menu([])]
  const edges = [{ id: 'start-menu', source: 'start', target: 'menu' }]

  const result = validateFlow(nodes, edges, 'telegram')

  assert.equal(result.ok, false)
  assert.ok(result.problems.some((problem) => problem.message.includes('хотя бы одну кнопку')))
})

test('requires an attached Mini App only for publication readiness', () => {
  const nodes = [
    trigger,
    {
      id: 'mini-app',
      data: {
        group: 'block',
        type: 'open_mini_app',
        params: { text: 'Откройте витрину', button_text: 'Открыть', save_as: 'cart' },
      },
    },
  ]
  const edges = [{ id: 'start-mini', source: 'start', target: 'mini-app' }]

  assert.equal(validateFlow(nodes, edges, 'telegram').ok, true)
  const publishReadiness = validateFlow(nodes, edges, 'telegram', { requireMiniApp: true, miniAppAttached: false })
  assert.equal(publishReadiness.ok, false)
  assert.ok(publishReadiness.problems.some((problem) => problem.nodeId === 'mini-app'))
})
