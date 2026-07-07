// Сериализация графа редактора в агрегат Flow — то, что уходит на backend как ДАННЫЕ.
// Именно эти данные интерпретирует Flow Engine в рантайме; редактор кода не генерит.

export function serializeFlow(nodes, edges, meta) {
  const triggers = nodes
    .filter((n) => n.data.group === 'trigger')
    .map((n) => ({ id: n.id, type: n.data.type }))

  const blocks = nodes
    .filter((n) => n.data.group === 'block')
    .map((n) => ({ id: n.id, type: n.data.type, params: n.data.params }))

  const transitions = edges.map((e) => ({
    from: e.source,
    to: e.target,
    on: e.sourceHandle || 'next', // next | true | false | callback
  }))

  return {
    bot: { name: meta.botName, platform: meta.platform },
    trigger: triggers[0] || null,
    triggers,
    nodes: blocks,
    transitions,
  }
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
