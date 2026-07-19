import assert from 'node:assert/strict'
import test from 'node:test'

import { deserializeDefinition, nextNodeIdNumber } from './deserialize.js'
import { serializeDefinition, validateFlow } from './serialize.js'
import { buttonHandleId } from './handles.js'

// Канонический definition (контракт src/domain/flow/codec.py): triggers,
// nodes с params после normalizeParams (json распарсен, number — число),
// buttons присутствуют у каждого узла, transitions с исходами.
function canonicalDefinition() {
  return {
    doc_schema_version: 1,
    triggers: [
      { id: 't_start', type: 'start', target_node_id: 'n1', config: {} },
      { id: 't_cb', type: 'callback', target_node_id: 'n2', config: { payload: 'go_menu' } },
    ],
    nodes: [
      { id: 'n1', type: 'send_message', params: { text: 'Привет, {name}!' }, buttons: [] },
      {
        id: 'n2',
        type: 'show_buttons',
        params: { text: 'Выберите действие:' },
        buttons: [
          { label: 'Дальше', action: 'next', target: 'n3' },
          { label: 'Сайт', action: 'url', target: 'https://example.com' },
          { label: 'Меню', action: 'callback', target: 'go_menu' },
        ],
      },
      {
        id: 'n3',
        type: 'http_request',
        params: {
          method: 'POST',
          url: 'https://api.example.com/ask',
          headers: { 'Content-Type': 'application/json' },
          body: { q: '{user_question}' },
          timeout: 10,
          response_map: { answer: 'choices.0.message.content' },
        },
        buttons: [],
      },
      { id: 'n4', type: 'condition', params: { expression: 'answer' }, buttons: [] },
      { id: 'n5', type: 'send_message', params: { text: 'Готово.' }, buttons: [] },
      {
        // Кнопки допустимы у любого узла (Node.buttons в домене), хотя каталог
        // не даёт их редактировать у ask — при загрузке они не должны теряться.
        id: 'n6',
        type: 'ask',
        params: { prompt: 'Что дальше?', save_as: 'next_step' },
        buttons: [{ label: 'Позже', action: 'callback', target: 'напишу позже' }],
      },
      {
        // Params шире каталога: values-форма save (стирание ПДн, BR-008) должна
        // пережить открытие и повторное сохранение без потерь.
        id: 'n7',
        type: 'save',
        params: { values: { req_name: '', req_task: '' } },
        buttons: [],
      },
    ],
    transitions: [
      { source_node_id: 'n1', target_node_id: 'n2', on: 'next' },
      { source_node_id: 'n3', target_node_id: 'n4', on: 'next' },
      { source_node_id: 'n3', target_node_id: 'n5', on: 'error' },
      { source_node_id: 'n4', target_node_id: 'n5', on: 'true' },
      { source_node_id: 'n4', target_node_id: 'n6', on: 'false' },
      { source_node_id: 'n5', target_node_id: 'n6', on: 'next' },
      { source_node_id: 'n6', target_node_id: 'n7', on: 'next' },
    ],
  }
}

test('round-trip: serializeDefinition(deserializeDefinition(def)) воспроизводит definition', () => {
  const definition = canonicalDefinition()
  const { nodes, edges } = deserializeDefinition(definition)
  assert.deepEqual(serializeDefinition(nodes, edges), definition)
})

test('восстановленный граф проходит validateFlow без проблем', () => {
  const { nodes, edges } = deserializeDefinition(canonicalDefinition())
  const result = validateFlow(nodes, edges, 'telegram')
  assert.deepEqual(result.problems, [])
  assert.equal(result.ok, true)
})

test('метаданные узлов приходят из каталога, json-параметры снова строки', () => {
  const { nodes } = deserializeDefinition(canonicalDefinition())
  const trigger = nodes.find((node) => node.id === 't_start')
  assert.equal(trigger.type, 'trigger')
  assert.equal(trigger.data.group, 'trigger')
  assert.equal(trigger.data.label, 'Команда /start')
  assert.equal(trigger.data.icon, '⚑')

  const http = nodes.find((node) => node.id === 'n3')
  assert.equal(typeof http.data.params.headers, 'string')
  assert.deepEqual(JSON.parse(http.data.params.headers), { 'Content-Type': 'application/json' })
  assert.equal(http.data.params.timeout, 10)
  assert.equal(http.data.params.method, 'POST')
})

test('пропущенные в definition поля остаются пустыми, а не демо-дефолтами каталога', () => {
  // У движка свои дефолты (http_request без method — GET): подстановка
  // каталожного POST/body при открытии меняла бы семантику при пересохранении.
  const definition = {
    doc_schema_version: 1,
    triggers: [{ id: 't1', type: 'start', target_node_id: 'n1', config: {} }],
    nodes: [{ id: 'n1', type: 'http_request', params: { url: 'https://api.example.com' }, buttons: [] }],
    transitions: [],
  }
  const { nodes, edges } = deserializeDefinition(definition)
  const params = nodes.find((node) => node.id === 'n1').data.params
  assert.equal(params.method, '')
  assert.equal(params.body, '')
  assert.equal(params.timeout, '')
  const roundTrip = serializeDefinition(nodes, edges).nodes[0].params
  assert.ok(!('method' in roundTrip), 'method не должен появиться из дефолтов каталога')
  assert.ok(!('timeout' in roundTrip))
  assert.equal(roundTrip.url, 'https://api.example.com')
})

test('дубли id и коллизия trigger/block схлопываются до первого вхождения', () => {
  const definition = {
    doc_schema_version: 1,
    triggers: [
      { id: 't1', type: 'start', target_node_id: 'n1', config: {} },
      { id: 't1', type: 'text', target_node_id: 'n1', config: { pattern: 'дубль' } },
    ],
    nodes: [
      { id: 'n1', type: 'send_message', params: { text: 'первый' }, buttons: [] },
      { id: 'n1', type: 'send_message', params: { text: 'дубль' }, buttons: [] },
      { id: 't1', type: 'send_message', params: { text: 'коллизия с триггером' }, buttons: [] },
    ],
    transitions: [],
  }
  const { nodes } = deserializeDefinition(definition)
  assert.deepEqual(nodes.map((node) => node.id), ['t1', 'n1'])
  assert.equal(nodes[0].data.group, 'trigger')
  assert.equal(nodes[1].data.params.text, 'первый')
})

test('кнопочные рёбра синтезируются только для action=next с существующей целью', () => {
  const { edges } = deserializeDefinition(canonicalDefinition())
  const buttonEdges = edges.filter((edge) => String(edge.sourceHandle || '').startsWith('button:'))
  assert.deepEqual(buttonEdges, [
    { source: 'n2', sourceHandle: buttonHandleId(0), target: 'n3' },
  ])
})

test('триггер без цели и переход в отсутствующий блок не порождают рёбер', () => {
  const definition = {
    doc_schema_version: 1,
    triggers: [{ id: 't1', type: 'start', target_node_id: null, config: {} }],
    nodes: [{ id: 'n1', type: 'send_message', params: { text: 'x' }, buttons: [] }],
    transitions: [{ source_node_id: 'n1', target_node_id: 'missing', on: 'next' }],
  }
  const { nodes, edges } = deserializeDefinition(definition)
  assert.equal(nodes.length, 2)
  assert.deepEqual(edges, [])
})

test('неизвестный тип блока не роняет десериализацию и сохраняет params', () => {
  const definition = {
    doc_schema_version: 1,
    triggers: [],
    nodes: [{ id: 'n1', type: 'mystery_block', params: { anything: 42 }, buttons: [] }],
    transitions: [],
  }
  const { nodes } = deserializeDefinition(definition)
  assert.equal(nodes[0].data.type, 'mystery_block')
  assert.deepEqual(nodes[0].data.params, { anything: 42 })
})

test('автолейаут детерминирован, позиции конечны и не совпадают', () => {
  const first = deserializeDefinition(canonicalDefinition())
  const second = deserializeDefinition(canonicalDefinition())
  assert.deepEqual(first, second)

  const seen = new Set()
  for (const node of first.nodes) {
    assert.ok(Number.isFinite(node.position.x) && Number.isFinite(node.position.y), `позиция ${node.id}`)
    const key = `${node.position.x}:${node.position.y}`
    assert.ok(!seen.has(key), `позиции ${node.id} совпали с другим узлом`)
    seen.add(key)
  }
})

test('недостижимые блоки укладываются ниже графа, а не теряются', () => {
  const definition = canonicalDefinition()
  definition.nodes.push({ id: 'n_orphan', type: 'send_message', params: { text: 'один' }, buttons: [] })
  const { nodes } = deserializeDefinition(definition)
  const orphan = nodes.find((node) => node.id === 'n_orphan')
  const reachableMaxY = Math.max(...nodes.filter((node) => node.id !== 'n_orphan').map((node) => node.position.y))
  assert.ok(orphan.position.y > reachableMaxY)
})

test('nextNodeIdNumber продолжает нумерацию только числовых id формата nNNN', () => {
  assert.equal(nextNodeIdNumber([]), 100)
  assert.equal(nextNodeIdNumber(['n_welcome', 't_start', 'x2']), 100)
  assert.equal(nextNodeIdNumber(['n105', 'n99', 'n_orphan']), 106)
  // id за пределами safe integer сломал бы счётчик (1e18 + 1 === 1e18) —
  // такие id игнорируются.
  assert.equal(nextNodeIdNumber(['n9007199254740993', 'n105']), 106)
})

test('save без values в definition получает пустой словарь в редакторе и не приобретает его при сохранении', () => {
  const definition = {
    doc_schema_version: 1,
    triggers: [{ id: 't1', type: 'start', target_node_id: 'n1', config: {} }],
    nodes: [{ id: 'n1', type: 'save', params: { key: 'lead', value: 'tg' }, buttons: [] }],
    transitions: [],
  }
  const { nodes, edges } = deserializeDefinition(definition)
  assert.deepEqual(nodes.find((node) => node.id === 'n1').data.params.values, {})
  assert.deepEqual(serializeDefinition(nodes, edges), definition)
})
