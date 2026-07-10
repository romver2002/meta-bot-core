function cloneValue(value) {
  if (value === undefined) return undefined
  if (typeof structuredClone === 'function') return structuredClone(value)
  return JSON.parse(JSON.stringify(value))
}

function cloneNodeData(data, idMap) {
  const nextData = cloneValue(data)
  const buttons = nextData.params?.buttons
  if (!Array.isArray(buttons)) return nextData

  nextData.params.buttons = buttons.map((button) => ({
    ...button,
    target: button.action === 'next' ? (idMap.get(button.target) || '') : button.target,
  }))
  return nextData
}

export function createBlockSelectionSnapshot(nodes, edges) {
  const selectedBlocks = nodes.filter((node) => node.selected && node.data?.group === 'block')
  if (selectedBlocks.length === 0) return null

  const selectedIds = new Set(selectedBlocks.map((node) => node.id))
  return {
    nodes: selectedBlocks.map((node) => cloneValue(node)),
    // Копируем только связи внутри группы. Внешние входы и выходы не должны
    // внезапно начать вести ещё и в новую ветку сценария.
    edges: edges.filter((edge) => selectedIds.has(edge.source) && selectedIds.has(edge.target)).map((edge) => cloneValue(edge)),
  }
}

export function pasteBlockSelectionSnapshot({
  nodes,
  edges,
  snapshot,
  createNodeId,
  createEdgeId,
  offset = { x: 48, y: 48 },
}) {
  if (!snapshot?.nodes?.length) return { nodes, edges, createdNodeIds: [] }

  const idMap = new Map(snapshot.nodes.map((node) => [node.id, createNodeId()]))
  const copiedNodes = snapshot.nodes.map((node) => ({
    ...cloneValue(node),
    id: idMap.get(node.id),
    position: {
      x: node.position.x + offset.x,
      y: node.position.y + offset.y,
    },
    selected: true,
    data: cloneNodeData(node.data, idMap),
  }))
  const copiedEdges = snapshot.edges.flatMap((edge) => {
    const source = idMap.get(edge.source)
    if (!source) return []

    const edgeData = cloneValue(edge.data) || {}
    delete edgeData.bend
    return [{
      ...cloneValue(edge),
      id: createEdgeId(edge),
      source,
      target: idMap.get(edge.target),
      selected: true,
      data: edgeData,
    }]
  })

  return {
    nodes: [...nodes.map((node) => ({ ...node, selected: false })), ...copiedNodes],
    edges: [...edges.map((edge) => ({ ...edge, selected: false })), ...copiedEdges],
    createdNodeIds: copiedNodes.map((node) => node.id),
  }
}
