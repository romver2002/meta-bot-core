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

test('quick-reply: callback-кнопка на ask не требует входа «Нажатие кнопки», на меню — требует', () => {
  const ask = {
    id: 'ask',
    data: {
      group: 'block',
      type: 'ask',
      params: {
        prompt: 'Бюджет?',
        save_as: 'budget',
        buttons: [{ label: 'До 10 тыс', action: 'callback', target: 'До 10 тыс' }],
      },
    },
  }
  const nodes = [trigger, ask]
  const edges = [{ id: 'start-ask', source: 'start', target: 'ask' }]
  assert.equal(validateFlow(nodes, edges, 'telegram').ok, true)

  const menuNodes = [
    trigger,
    menu([{ label: 'До 10 тыс', action: 'callback', target: 'До 10 тыс' }]),
  ]
  const menuEdges = [{ id: 'start-menu', source: 'start', target: 'menu' }]
  const result = validateFlow(menuNodes, menuEdges, 'telegram')
  assert.equal(result.ok, false)
  assert.ok(result.problems.some((problem) => problem.message.includes('нет входа «Нажатие кнопки»')))
})

test('save в форме values-словаря валиден без пары «Ключ/Значение» и не теряет params', () => {
  const wipe = {
    id: 'wipe',
    data: {
      group: 'block',
      type: 'save',
      params: { key: '', value: '', values: { name: '', task: '' } },
    },
  }
  const nodes = [trigger, wipe]
  const edges = [{ id: 'start-wipe', source: 'start', target: 'wipe' }]
  assert.equal(validateFlow(nodes, edges, 'telegram').ok, true)
  assert.deepEqual(serializeDefinition(nodes, edges).nodes[0].params, { values: { name: '', task: '' } })
})

test('save с values-словарём И заполненным «Ключ/Значение» подсвечивает конфликт', () => {
  const conflicted = {
    id: 'wipe',
    data: {
      group: 'block',
      type: 'save',
      params: { key: 'source', value: 'tg', values: { name: '' } },
    },
  }
  const nodes = [trigger, conflicted]
  const edges = [{ id: 'start-wipe', source: 'start', target: 'wipe' }]
  const result = validateFlow(nodes, edges, 'telegram')
  assert.equal(result.ok, false)
  assert.ok(result.problems.some((problem) => problem.nodeId === 'wipe' && problem.message.includes('values-словарь')))
})
