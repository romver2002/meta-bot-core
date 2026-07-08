// Сериализация графа редактора в definition — контракт хранения бэкенда
// (src/infrastructure/db/mappers.py, ADR-0008): ровно этот JSON сохраняется в
// flow_versions.definition и интерпретируется Flow Engine.
// SSoT формата — specs/001-persistence/design.md.

export const DOC_SCHEMA_VERSION = 1

export function serializeFlow(nodes, edges, meta) {
  const triggerNodes = nodes.filter((n) => n.data.group === 'trigger')
  const blockNodes = nodes.filter((n) => n.data.group === 'block')
  const blockIds = new Set(blockNodes.map((n) => n.id))

  const definition = {
    doc_schema_version: DOC_SCHEMA_VERSION,
    triggers: triggerNodes.map((t) => ({
      id: t.id,
      type: t.data.type,
      // Вход в сценарий: первое ребро от триггера ведёт в стартовый узел.
      target_node_id: edges.find((e) => e.source === t.id)?.target ?? null,
      config: {},
    })),
    nodes: blockNodes.map((n) => ({
      id: n.id,
      type: n.data.type,
      params: withoutButtons(n.data.params),
      buttons: (n.data.params.buttons ?? []).map((b) => ({
        label: b.label,
        action: b.action,
        target: b.target ?? null,
      })),
    })),
    // Переходы — только между блоками; рёбра от триггеров уже учтены выше.
    transitions: edges
      .filter((e) => blockIds.has(e.source) && blockIds.has(e.target))
      .map((e) => ({
        source_node_id: e.source,
        target_node_id: e.target,
        on: e.sourceHandle || 'next',
      })),
  }

  return {
    bot: { name: meta.botName, platform: meta.platform },
    definition,
  }
}

function withoutButtons(params = {}) {
  const { buttons: _buttons, ...rest } = params
  return rest
}

// Проверка публикуемости (упрощённо, по BR-001): есть триггер входа и хотя бы один блок.
export function validateFlow(nodes) {
  const problems = []
  const hasTrigger = nodes.some((n) => n.data.group === 'trigger')
  const hasBlock = nodes.some((n) => n.data.group === 'block')
  if (!hasTrigger) problems.push('Нет ни одного триггера входа (BR-001)')
  if (!hasBlock) problems.push('Сценарий пуст — добавьте хотя бы один блок (BR-001)')
  return { ok: problems.length === 0, problems }
}
