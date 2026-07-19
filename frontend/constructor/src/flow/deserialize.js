// Обратная сторона serialize.js: definition (канонический контракт
// src/domain/flow/codec.py) -> узлы и рёбра React Flow. Позиции узлов в
// definition не хранятся (кодек отбрасывает неизвестные поля при сохранении),
// поэтому раскладка восстанавливается детерминированным послойным автолейаутом
// от триггеров вглубь сценария.
import { BLOCK_BY_TYPE, TRIGGER_BY_TYPE } from '../domain/catalog.js'
import { buttonHandleId } from './handles.js'

const LAYOUT = { baseX: 420, stepX: 270, baseY: 0, stepY: 180, orphansPerRow: 4 }

export function deserializeDefinition(definition) {
  // Дубли id (кодек их не запрещает) схлопываются до первого вхождения:
  // React Flow с двумя одинаковыми id теряет узлы и сыпет ошибки.
  const triggers = dedupeById(asArray(definition?.triggers))
  const seenTriggerIds = new Set(triggers.map((trigger) => trigger.id))
  const blocks = dedupeById(asArray(definition?.nodes)).filter((block) => !seenTriggerIds.has(block.id))
  const transitions = asArray(definition?.transitions)
  const blockIds = new Set(blocks.map((block) => block.id))

  const edges = []
  for (const trigger of triggers) {
    if (trigger.target_node_id && blockIds.has(trigger.target_node_id)) {
      edges.push({ source: trigger.id, target: trigger.target_node_id })
    }
  }
  for (const block of blocks) {
    asArray(block.buttons).forEach((button, index) => {
      if (button.action === 'next' && button.target && blockIds.has(button.target)) {
        edges.push({ source: block.id, sourceHandle: buttonHandleId(index), target: button.target })
      }
    })
  }
  for (const transition of transitions) {
    if (blockIds.has(transition.source_node_id) && blockIds.has(transition.target_node_id)) {
      edges.push({
        source: transition.source_node_id,
        sourceHandle: transition.on || 'next',
        target: transition.target_node_id,
      })
    }
  }

  const positions = layoutPositions(triggers, blocks, edges)
  const nodes = [
    ...triggers.map((trigger) => triggerNode(trigger, positions.get(trigger.id))),
    ...blocks.map((block) => blockNode(block, positions.get(block.id))),
  ]
  return { nodes, edges }
}

// Счётчик newId в редакторе должен продолжать нумерацию загруженных узлов,
// иначе новый блок получит id существующего (n100, n101, ...).
export function nextNodeIdNumber(ids) {
  let next = 100
  for (const id of ids) {
    const match = /^n(\d+)$/.exec(id)
    if (!match) continue
    const value = Number(match[1])
    // За пределами safe integer инкремент теряется (1e18 + 1 === 1e18) и все
    // новые узлы получили бы один id — такие id счётчик не двигают.
    if (Number.isSafeInteger(value + 1)) next = Math.max(next, value + 1)
  }
  return next
}

function dedupeById(items) {
  const seen = new Set()
  return items.filter((item) => {
    if (seen.has(item.id)) return false
    seen.add(item.id)
    return true
  })
}

function triggerNode(trigger, position) {
  const def = TRIGGER_BY_TYPE[trigger.type]
  return {
    id: trigger.id,
    type: 'trigger',
    position,
    data: {
      group: 'trigger',
      type: trigger.type,
      label: def?.label || trigger.type,
      icon: def?.icon || '⚑',
      config: { ...(trigger.config || {}) },
    },
  }
}

function blockNode(block, position) {
  return {
    id: block.id,
    type: 'block',
    position,
    data: { group: 'block', type: block.type, params: editorParams(block) },
  }
}

// definition хранит params после normalizeParams (json распарсен, number —
// число); поля редактора восстанавливаются поверх дефолтов каталога.
function editorParams(block) {
  const def = BLOCK_BY_TYPE[block.type]
  const source = block.params || {}
  const buttons = asArray(block.buttons).map((button) => ({
    label: button.label ?? '',
    action: button.action ?? 'next',
    target: button.target ?? '',
  }))
  if (!def?.fields) {
    // Неизвестный конструктору тип: params не трогаем, чтобы не потерять данные;
    // BlockNode отрисует такой узел как «Неизвестный блок», validateFlow подсветит.
    return { ...source, ...(buttons.length > 0 ? { buttons } : {}) }
  }
  // Отсутствующий в definition ключ остаётся ПУСТЫМ, а не демо-дефолтом
  // каталога: у движка свои дефолты (например, http_request без method — GET,
  // process_update.py), и подстановка образца body/method при открытии молча
  // меняла бы семантику сценария при повторном сохранении.
  const params = {}
  const catalogKeys = new Set(['buttons'])
  let buttonsAssigned = false
  for (const field of def.fields) {
    catalogKeys.add(field.key)
    if (field.kind === 'buttons' || field.kind === 'quick_replies') {
      params[field.key] = buttons
      buttonsAssigned = true
      continue
    }
    if (!(field.key in source)) {
      params[field.key] = field.kind === 'kv' ? {} : ''
      continue
    }
    const value = source[field.key]
    params[field.key] = field.kind === 'json'
      ? (value === null ? '' : JSON.stringify(value, null, 2))
      : value
  }
  // Params шире каталога (например, values у save) проходят насквозь как есть —
  // редактор их не показывает, но normalizeParams вернёт их без потерь.
  for (const [key, value] of Object.entries(source)) {
    if (!catalogKeys.has(key)) params[key] = value
  }
  // Движок допускает кнопки у любого узла (Node.buttons в домене), а каталог
  // показывает редактор кнопок не для всех типов — данные не теряем:
  // serialize.js читает params.buttons у любого блока.
  if (!buttonsAssigned && buttons.length > 0) params.buttons = buttons
  return params
}

// Послойный автолейаут: триггеры — слой 0, дальше BFS по рёбрам; блоки,
// недостижимые от триггеров, докладываются рядами ниже графа.
function layoutPositions(triggers, blocks, edges) {
  const outgoing = new Map()
  for (const edge of edges) {
    if (!outgoing.has(edge.source)) outgoing.set(edge.source, [])
    outgoing.get(edge.source).push(edge.target)
  }

  const layerOf = new Map()
  const visitOrder = triggers.map((trigger) => trigger.id)
  for (const id of visitOrder) layerOf.set(id, 0)
  for (let cursor = 0; cursor < visitOrder.length; cursor += 1) {
    const id = visitOrder[cursor]
    for (const next of outgoing.get(id) || []) {
      if (layerOf.has(next)) continue
      layerOf.set(next, layerOf.get(id) + 1)
      visitOrder.push(next)
    }
  }

  let maxLayer = 0
  for (const layer of layerOf.values()) maxLayer = Math.max(maxLayer, layer)
  const orphans = blocks.filter((block) => !layerOf.has(block.id))
  orphans.forEach((block, index) => {
    layerOf.set(block.id, maxLayer + 1 + Math.floor(index / LAYOUT.orphansPerRow))
    visitOrder.push(block.id)
  })

  const rows = new Map()
  for (const id of visitOrder) {
    const layer = layerOf.get(id)
    if (!rows.has(layer)) rows.set(layer, [])
    rows.get(layer).push(id)
  }

  const positions = new Map()
  for (const [layer, ids] of rows) {
    ids.forEach((id, index) => {
      positions.set(id, {
        x: LAYOUT.baseX + (index - (ids.length - 1) / 2) * LAYOUT.stepX,
        y: LAYOUT.baseY + layer * LAYOUT.stepY,
      })
    })
  }
  return positions
}

function asArray(value) {
  return Array.isArray(value) ? value : []
}
