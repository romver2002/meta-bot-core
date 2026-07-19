import { BLOCK_BY_TYPE, PLATFORMS, TRIGGER_BY_TYPE, blockAvailable } from '../domain/catalog.js'
import { buttonHandleId, isButtonEdge } from './handles.js'

export const DOC_SCHEMA_VERSION = 1

const TRANSITIONAL_BLOCKS = new Set([
  'send_message',
  'ask',
  'condition',
  'open_mini_app',
  'save',
  'http_request',
  'notify',
])

const BUTTON_ACTIONS = new Set(['next', 'callback', 'open_mini_app', 'url'])

// Платформенные лимиты callback-payload в байтах (platform-reference.md):
// Telegram callback_data — 1–64 байта, MAX payload — до 1024.
const CALLBACK_PAYLOAD_BYTE_LIMITS = { telegram: 64, max: 1024 }

// Ключи переменных подставляются в текст только как {ascii_identifier}
// (domain/flow/interpolation.py) — прочие имена молча не отрендерятся.
const VARIABLE_NAME = /^[a-zA-Z_][a-zA-Z0-9_]*$/

export function serializeFlow(nodes, edges, meta) {
  return {
    bot: { name: meta.botName, platform: meta.platform },
    definition: serializeDefinition(nodes, edges),
  }
}

export function serializeDefinition(nodes, edges) {
  const triggerNodes = nodes.filter((node) => node.data.group === 'trigger')
  const blockNodes = nodes.filter((node) => node.data.group === 'block')
  const blockIds = new Set(blockNodes.map((node) => node.id))
  const nodeById = new Map(nodes.map((node) => [node.id, node]))

  return {
    doc_schema_version: DOC_SCHEMA_VERSION,
    triggers: triggerNodes.map((trigger) => ({
      id: trigger.id,
      type: trigger.data.type,
      target_node_id: edges.find((edge) => edge.source === trigger.id)?.target ?? null,
      config: cleanObject(trigger.data.config || {}),
    })),
    nodes: blockNodes.map((node) => ({
      id: node.id,
      type: node.data.type,
      params: normalizeParams(node.data.type, node.data.params).params,
      buttons: (node.data.params.buttons ?? []).map((button) => ({
        label: button.label,
        action: button.action,
        target: button.target ?? null,
      })),
    })),
    transitions: edges
      .filter((edge) => blockIds.has(edge.source) && blockIds.has(edge.target))
      .filter((edge) => !isButtonEdge(edge))
      .filter((edge) => TRANSITIONAL_BLOCKS.has(nodeById.get(edge.source)?.data.type))
      .map((edge) => ({
        source_node_id: edge.source,
        target_node_id: edge.target,
        on: edge.sourceHandle || 'next',
      })),
  }
}

export function validateFlow(nodes, edges, platformId, options = {}) {
  const { requireMiniApp = false, miniAppAttached = false } = options
  const problems = []
  const triggerNodes = nodes.filter((node) => node.data.group === 'trigger')
  const blockNodes = nodes.filter((node) => node.data.group === 'block')
  const nodeById = new Map(nodes.map((node) => [node.id, node]))
  const blockIds = new Set(blockNodes.map((node) => node.id))
  const triggerIds = new Set(triggerNodes.map((node) => node.id))

  if (triggerNodes.length === 0) addProblem(problems, 'Добавьте хотя бы один вход в сценарий (BR-001)')
  if (blockNodes.length === 0) addProblem(problems, 'Сценарий пуст — добавьте хотя бы один блок (BR-001)')

  for (const trigger of triggerNodes) {
    const outgoing = edges.filter((edge) => edge.source === trigger.id)
    const target = outgoing[0]?.target
    if (!target || !blockIds.has(target)) {
      addProblem(problems, `${triggerLabel(trigger)} не связан с существующим блоком`, trigger.id)
    }
    if (outgoing.length > 1) {
      addProblem(problems, `${triggerLabel(trigger)} должен вести только в один блок`, trigger.id)
    }
  }

  const callbackPayloads = new Set(
    triggerNodes
      .filter((trigger) => trigger.data.type === 'callback')
      .map((trigger) => trigger.data.config?.payload)
      .filter(Boolean),
  )

  for (const node of blockNodes) {
    const def = BLOCK_BY_TYPE[node.data.type]
    if (!def) {
      addProblem(problems, `${nodeLabel(node)}: неизвестный тип блока`, node.id)
      continue
    }
    if (!blockAvailable(def, platformId)) {
      addProblem(problems, `${nodeLabel(node)} недоступен на ${PLATFORMS[platformId]?.label || platformId} (BR-006)`, node.id)
    }
    if (node.data.type === 'custom_code') {
      addProblem(problems, `${nodeLabel(node)} пока не поддерживается Flow Engine`, node.id)
    }

    const normalized = normalizeParams(node.data.type, node.data.params)
    for (const message of normalized.problems) addProblem(problems, `${nodeLabel(node)}: ${message}`, node.id)

    // Блок save валиден и в форме values-словаря (несколько переменных одним
    // узлом, в т.ч. стирание ПДн — BR-008, process_update.py); тогда пара
    // «Ключ/Значение» из каталога не обязательна. Пустой {} — не форма values.
    const savesValuesMap = node.data.type === 'save'
      && node.data.params.values !== null
      && node.data.params.values !== undefined
      && typeof node.data.params.values === 'object'
      && !Array.isArray(node.data.params.values)
      && Object.keys(node.data.params.values).length > 0
    for (const field of def.fields || []) {
      if (field.kind === 'buttons' || field.kind === 'quick_replies' || field.kind === 'kv') continue
      if (savesValuesMap && field.key === 'key') continue
      if (field.required && !String(node.data.params[field.key] ?? '').trim()) {
        addProblem(problems, `${nodeLabel(node)}: заполните «${field.label}»`, node.id)
      }
    }
    // При values-словаре движок исполняет ТОЛЬКО его (process_update.py):
    // заполненная рядом пара «Ключ/Значение» молча не исполнилась бы.
    if (savesValuesMap
      && (String(node.data.params.key ?? '').trim() || String(node.data.params.value ?? '').trim())) {
      addProblem(problems, `${nodeLabel(node)}: узел исполняет values-словарь — уберите «Ключ/Значение» или сам словарь`, node.id)
    }
    // Имя переменной, не подходящее под {identifier}, никогда не подставится
    // в текст (interpolation.py) — записывать его почти наверняка ошибка.
    if (node.data.type === 'save') {
      const variableNames = savesValuesMap
        ? Object.keys(node.data.params.values)
        : [String(node.data.params.key ?? '').trim()].filter(Boolean)
      for (const name of variableNames) {
        if (!VARIABLE_NAME.test(name)) {
          addProblem(problems, `${nodeLabel(node)}: переменная «${name}» не подставится в {…} — допустимы латиница, цифры и «_»`, node.id)
        }
      }
    }

    const buttons = Array.isArray(node.data.params.buttons) ? node.data.params.buttons : []
    if (node.data.type === 'show_buttons' && buttons.length === 0) {
      addProblem(problems, `${nodeLabel(node)}: добавьте хотя бы одну кнопку`, node.id)
    }

    for (const [index, button] of buttons.entries()) {
      const prefix = `${nodeLabel(node)}: кнопка «${button.label || index + 1}»`
      if (!String(button.label || '').trim()) addProblem(problems, `${prefix} без подписи`, node.id)
      if (!BUTTON_ACTIONS.has(button.action)) {
        addProblem(problems, `${prefix}: неизвестное действие`, node.id)
        continue
      }
      // Назначение из одних пробелов ушло бы в payload и молча стало бы
      // «ответом» пользователя — считаем его пустым.
      if (!String(button.target || '').trim()) addProblem(problems, `${prefix}: укажите назначение`, node.id)
      if (button.action === 'callback' && button.target) {
        const limit = CALLBACK_PAYLOAD_BYTE_LIMITS[platformId]
        const bytes = new TextEncoder().encode(button.target).length
        if (limit && bytes > limit) {
          addProblem(problems, `${prefix}: значение длиннее ${limit} байт — ${PLATFORMS[platformId]?.label || platformId} не отправит кнопку (сейчас ${bytes})`, node.id)
        }
      }
      if (button.action === 'next' && button.target && !blockIds.has(button.target)) {
        addProblem(problems, `${prefix} ведёт в отсутствующий блок`, node.id)
      }
      if (button.action === 'next' && button.target && blockIds.has(button.target)) {
        const visible = edges.some((edge) => (
          edge.source === node.id
          && edge.sourceHandle === buttonHandleId(index)
          && edge.target === button.target
        ))
        if (!visible) addProblem(problems, `${prefix}: добавьте связь на холсте`, node.id)
      }
      // Callback-кнопка на ask — быстрый ответ: движок сохраняет payload как
      // ответ пользователя (process_update, «быстрый ответ равноправен
      // набранному тексту»), вход «Нажатие кнопки» для него не нужен.
      if (button.action === 'callback' && button.target && node.data.type !== 'ask' && !callbackPayloads.has(button.target)) {
        addProblem(problems, `${prefix}: нет входа «Нажатие кнопки» с payload «${button.target}»`, node.id)
      }
      // Обратная коллизия: значение быстрого ответа, совпадающее с payload
      // входа, перехватит навигацию — пока блок ждёт ответ, движок сохранит
      // payload как ответ и до входа дело не дойдёт (_ask_option_answer
      // проверяется раньше триггеров).
      if (button.action === 'callback' && button.target && node.data.type === 'ask' && callbackPayloads.has(button.target)) {
        addProblem(problems, `${prefix}: значение «${button.target}» совпадает с payload входа «Нажатие кнопки» — во время вопроса такая кнопка сработает как ответ, а не как переход`, node.id)
      }
      if ((button.action === 'url' || button.action === 'open_mini_app') && button.target && !button.target.startsWith('https://')) {
        addProblem(problems, `${prefix}: URL должен начинаться с https://`, node.id)
      }
    }
  }

  const outcomes = new Set()
  for (const edge of edges) {
    if (triggerIds.has(edge.source)) continue
    if (!blockIds.has(edge.source) || !blockIds.has(edge.target)) {
      addProblem(problems, 'Связь должна соединять два существующих блока', edge.source)
      continue
    }
    if (isButtonEdge(edge)) continue

    const source = nodeById.get(edge.source)
    const sourceType = source?.data.type
    if (!TRANSITIONAL_BLOCKS.has(sourceType)) {
      addProblem(problems, `${nodeLabel(source)}: переход задаётся через кнопку`, edge.source)
      continue
    }
    const outcome = edge.sourceHandle || 'next'
    const allowedOutcomes = BLOCK_BY_TYPE[sourceType]?.outputs || []
    if (!allowedOutcomes.includes(outcome)) {
      addProblem(problems, `${nodeLabel(source)}: недопустимый исход «${outcome}»`, edge.source)
      continue
    }
    const key = `${edge.source}:${outcome}`
    if (outcomes.has(key)) {
      addProblem(problems, `${nodeLabel(source)}: для исхода «${outcome}» может быть только один переход`, edge.source)
    }
    outcomes.add(key)
  }

  if (requireMiniApp && !miniAppAttached) {
    const miniAppNode = blockNodes.find((node) => node.data.type === 'open_mini_app')
    if (miniAppNode) {
      addProblem(problems, 'Перед публикацией привяжите к боту Mini App с HTTPS-адресом', miniAppNode.id)
    }
  }

  const unreachable = findUnreachable(blockNodes, triggerNodes, edges)
  if (unreachable.length > 0) {
    addProblem(problems, `Недостижимые блоки: ${unreachable.map((id) => nodeLabel(nodeById.get(id))).join(', ')}`)
  }

  return { ok: problems.length === 0, problems }
}

export function normalizeParams(type, params = {}) {
  const def = BLOCK_BY_TYPE[type]
  const result = {}
  const problems = []
  const catalogKeys = new Set(['buttons'])
  for (const field of def?.fields || []) {
    catalogKeys.add(field.key)
    // Кнопки (обычные и быстрые ответы) живут на уровне узла definition,
    // не в params — их эмитит serializeDefinition.
    if (field.kind === 'buttons' || field.kind === 'quick_replies') continue
    const raw = params[field.key]
    if (field.kind === 'kv') {
      // Словарь пишется только непустым: пустой {} перебил бы пару
      // «Ключ/Значение» у движка (isinstance dict побеждает). Осознанный
      // компромисс: authored-через-API values:{} рядом с key/value (no-op)
      // при пересохранении из редактора станет исполняемой парой.
      if (raw !== null && typeof raw === 'object' && !Array.isArray(raw) && Object.keys(raw).length > 0) {
        result[field.key] = raw
      }
      continue
    }
    if (field.kind === 'json') {
      const parsed = parseJson(raw, field)
      if (parsed.ok) result[field.key] = parsed.value
      else problems.push(`${field.label}: ${parsed.error}`)
    } else if (field.kind === 'number') {
      // Пустое поле — отсутствие ключа (у движка свои дефолты), а не Number('') === 0.
      if (raw === '' || raw === undefined || raw === null) continue
      const value = Number(raw)
      if (Number.isFinite(value)) result[field.key] = value
      else problems.push(`${field.label}: должно быть число`)
    } else if (raw !== undefined && raw !== '') {
      result[field.key] = raw
    }
  }
  // Движок принимает params шире каталога (например, values у save —
  // process_update.py). Незнакомые редактору ключи проходят насквозь без
  // изменений, чтобы сохранение из редактора не теряло данные сценария.
  for (const [key, value] of Object.entries(params)) {
    if (!catalogKeys.has(key)) result[key] = value
  }
  return { params: result, problems }
}

function parseJson(raw, field) {
  if (raw === undefined || raw === null || raw === '') {
    return { ok: true, value: field.jsonType === 'object' ? {} : null }
  }
  try {
    const value = typeof raw === 'string' ? JSON.parse(raw) : raw
    if (field.jsonType === 'object' && (value === null || Array.isArray(value) || typeof value !== 'object')) {
      return { ok: false, error: 'ожидается JSON object' }
    }
    return { ok: true, value }
  } catch (error) {
    return { ok: false, error: error.message }
  }
}

function findUnreachable(blockNodes, triggerNodes, edges) {
  const blockIds = new Set(blockNodes.map((node) => node.id))
  const adjacency = new Map(blockNodes.map((node) => [node.id, new Set()]))
  const queue = []

  for (const edge of edges) {
    if (blockIds.has(edge.source) && blockIds.has(edge.target)) adjacency.get(edge.source).add(edge.target)
    if (triggerNodes.some((node) => node.id === edge.source) && blockIds.has(edge.target)) queue.push(edge.target)
  }
  for (const node of blockNodes) {
    for (const button of node.data.params.buttons || []) {
      if (button.action === 'next' && blockIds.has(button.target)) adjacency.get(node.id).add(button.target)
    }
  }

  const visited = new Set()
  for (let cursor = 0; cursor < queue.length; cursor += 1) {
    const id = queue[cursor]
    if (visited.has(id)) continue
    visited.add(id)
    for (const next of adjacency.get(id) || []) {
      if (!visited.has(next)) queue.push(next)
    }
  }
  return [...blockIds].filter((id) => !visited.has(id)).sort()
}

function addProblem(problems, message, nodeId = null) {
  problems.push({ message, nodeId })
}

function nodeLabel(node) {
  if (!node) return 'Блок'
  const def = BLOCK_BY_TYPE[node.data?.type]
  return `«${def?.label || node.data?.type || node.id}»`
}

function triggerLabel(trigger) {
  const def = TRIGGER_BY_TYPE[trigger.data.type]
  return `Вход «${def?.label || trigger.data.type}»`
}

function cleanObject(value) {
  return Object.fromEntries(Object.entries(value).filter(([, item]) => item !== undefined && item !== null && item !== ''))
}
