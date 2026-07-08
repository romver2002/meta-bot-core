import { BLOCK_BY_TYPE, PLATFORMS, blockAvailable } from '../domain/catalog.js'

export const DOC_SCHEMA_VERSION = 1

const TRANSITIONAL_BLOCKS = new Set(['send_message', 'ask', 'condition', 'open_mini_app', 'save', 'http_request'])

export function serializeFlow(nodes, edges, meta) {
  const triggerNodes = nodes.filter((node) => node.data.group === 'trigger')
  const blockNodes = nodes.filter((node) => node.data.group === 'block')
  const blockIds = new Set(blockNodes.map((node) => node.id))

  const definition = {
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
      .filter((edge) => TRANSITIONAL_BLOCKS.has(nodes.find((node) => node.id === edge.source)?.data.type))
      .map((edge) => ({
        source_node_id: edge.source,
        target_node_id: edge.target,
        on: edge.sourceHandle || 'next',
      })),
  }

  return {
    bot: { name: meta.botName, platform: meta.platform },
    definition,
  }
}

export function validateFlow(nodes, edges, platformId) {
  const problems = []
  const triggerNodes = nodes.filter((node) => node.data.group === 'trigger')
  const blockNodes = nodes.filter((node) => node.data.group === 'block')
  const blockIds = new Set(blockNodes.map((node) => node.id))
  const triggerIds = new Set(triggerNodes.map((node) => node.id))

  if (triggerNodes.length === 0) problems.push('Нет ни одного триггера входа (BR-001)')
  if (blockNodes.length === 0) problems.push('Сценарий пуст — добавьте хотя бы один блок (BR-001)')

  for (const trigger of triggerNodes) {
    const target = edges.find((edge) => edge.source === trigger.id)?.target
    if (!target || !blockIds.has(target)) problems.push(`Триггер ${trigger.id} не ведёт в существующий блок`)
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
      problems.push(`Неизвестный блок ${node.data.type}`)
      continue
    }
    if (!blockAvailable(def, platformId)) problems.push(`Блок ${def.label} недоступен на ${PLATFORMS[platformId]?.label || platformId} (BR-006)`)
    if (node.data.type === 'custom_code') problems.push('custom_code не входит в Engine v1 capabilities')

    const normalized = normalizeParams(node.data.type, node.data.params)
    problems.push(...normalized.problems.map((problem) => `${node.id}: ${problem}`))

    for (const field of def.fields || []) {
      if (field.required && !String(node.data.params[field.key] ?? '').trim()) {
        problems.push(`${node.id}: заполните поле «${field.label}»`)
      }
    }

    for (const [index, button] of (node.data.params.buttons || []).entries()) {
      const prefix = `${node.id}: кнопка ${index + 1}`
      if (!String(button.label || '').trim()) problems.push(`${prefix} без подписи`)
      if (!button.target) problems.push(`${prefix} без target`)
      if (button.action === 'next' && button.target && !blockIds.has(button.target)) {
        problems.push(`${prefix} ведёт в несуществующий блок ${button.target}`)
      }
      if (button.action === 'callback' && button.target && !callbackPayloads.has(button.target)) {
        problems.push(`${prefix}: нет callback-триггера с payload=${button.target}`)
      }
      if ((button.action === 'url' || button.action === 'open_mini_app') && button.target && !button.target.startsWith('https://')) {
        problems.push(`${prefix}: URL должен начинаться с https://`)
      }
    }
  }

  const outcomes = new Set()
  for (const edge of edges) {
    if (triggerIds.has(edge.source)) continue
    if (!blockIds.has(edge.source) || !blockIds.has(edge.target)) continue
    const source = nodes.find((node) => node.id === edge.source)
    if (!TRANSITIONAL_BLOCKS.has(source?.data.type)) {
      problems.push(`${edge.source}: этот блок не использует transition; задайте target у кнопки`)
      continue
    }
    const outcome = `${edge.source}:${edge.sourceHandle || 'next'}`
    if (outcomes.has(outcome)) problems.push(`${edge.source}: больше одного transition для исхода ${edge.sourceHandle || 'next'}`)
    outcomes.add(outcome)
  }

  const unreachable = findUnreachable(nodes, edges)
  if (unreachable.length > 0) problems.push(`Недостижимые узлы: ${unreachable.join(', ')}`)

  return { ok: problems.length === 0, problems }
}

export function normalizeParams(type, params = {}) {
  const def = BLOCK_BY_TYPE[type]
  const result = {}
  const problems = []
  for (const field of def?.fields || []) {
    if (field.kind === 'buttons') continue
    const raw = params[field.key]
    if (field.kind === 'json') {
      const parsed = parseJson(raw, field)
      if (parsed.ok) result[field.key] = parsed.value
      else problems.push(`${field.label}: ${parsed.error}`)
    } else if (field.kind === 'number') {
      const value = Number(raw)
      if (Number.isFinite(value)) result[field.key] = value
      else if (raw !== '' && raw !== undefined && raw !== null) problems.push(`${field.label}: должно быть число`)
    } else if (raw !== undefined && raw !== '') {
      result[field.key] = raw
    }
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

function cleanObject(value) {
  return Object.fromEntries(Object.entries(value).filter(([, item]) => item !== undefined && item !== null && item !== ''))
}

function findUnreachable(nodes, edges) {
  const blockNodes = nodes.filter((node) => node.data.group === 'block')
  const blockIds = new Set(blockNodes.map((node) => node.id))
  const adjacency = Object.fromEntries(blockNodes.map((node) => [node.id, new Set()]))
  const queue = []

  for (const edge of edges) {
    if (blockIds.has(edge.source) && blockIds.has(edge.target)) adjacency[edge.source]?.add(edge.target)
    if (nodes.find((node) => node.id === edge.source)?.data.group === 'trigger' && blockIds.has(edge.target)) queue.push(edge.target)
  }

  for (const node of blockNodes) {
    for (const button of node.data.params.buttons || []) {
      if (button.action === 'next' && blockIds.has(button.target)) adjacency[node.id].add(button.target)
    }
  }

  const visited = new Set()
  while (queue.length > 0) {
    const id = queue.shift()
    if (visited.has(id)) continue
    visited.add(id)
    for (const next of adjacency[id] || []) {
      if (!visited.has(next)) queue.push(next)
    }
  }

  return [...blockIds].filter((id) => !visited.has(id)).sort()
}
