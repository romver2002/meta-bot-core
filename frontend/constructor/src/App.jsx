import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  MarkerType,
  SelectionMode,
  addEdge,
  reconnectEdge,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import BlockNode from './components/nodes/BlockNode.jsx'
import TriggerNode from './components/nodes/TriggerNode.jsx'
import AdaptiveEdge from './components/edges/AdaptiveEdge.jsx'
import Palette from './components/Palette.jsx'
import ConfigPanel from './components/ConfigPanel.jsx'
import TopBar from './components/TopBar.jsx'
import JsonDrawer from './components/JsonDrawer.jsx'
import ApiPanel from './components/ApiPanel.jsx'
import { initialNodes, initialEdges } from './flow/initialFlow.js'
import { buttonIndexFromHandle, isButtonEdge } from './flow/handles.js'
import { createBlockSelectionSnapshot, pasteBlockSelectionSnapshot } from './flow/selection.js'
import { serializeDefinition, validateFlow } from './flow/serialize.js'
import { BLOCK_BY_TYPE, OUTCOME_LABELS, makeDefaultParams } from './domain/catalog.js'

let counter = 100

const newId = () => `n${counter++}`
const newEdgeId = () => `e-${newId()}`
const initialPaletteOpen = () => (typeof window === 'undefined' ? true : window.innerWidth > 900)
const isCompactViewport = () => typeof window !== 'undefined' && window.innerWidth <= 900
const OUTCOME_COLORS = { next: '#2563EB', true: '#16A34A', false: '#64748B', error: '#DC2626' }
const initialPresentationEdges = initialEdges.map((edge) => ({
  ...edge,
  type: 'adaptive',
  reconnectable: 'target',
  data: { ...edge.data },
}))

function isEditableTarget(target) {
  return target instanceof HTMLElement && Boolean(target.closest('input, textarea, select, [contenteditable="true"]'))
}

function plural(value, forms) {
  const remainder = Math.abs(value) % 100
  const lastDigit = remainder % 10
  if (remainder > 10 && remainder < 20) return forms[2]
  if (lastDigit > 1 && lastDigit < 5) return forms[1]
  if (lastDigit === 1) return forms[0]
  return forms[2]
}

function presentationEdge(connection, nodes) {
  const source = nodes.find((node) => node.id === connection.source)
  const buttonIndex = buttonIndexFromHandle(connection.sourceHandle)
  const id = connection.id || `e-${connection.source}-${connection.sourceHandle || 'next'}-${connection.target}`
  if (buttonIndex !== null) {
    const button = source?.data.params?.buttons?.[buttonIndex]
    const color = '#4F46E5'
    return {
      ...connection,
      id,
      type: 'adaptive',
      reconnectable: 'target',
      data: { ...connection.data },
      label: button?.label || `Кнопка ${buttonIndex + 1}`,
      style: { stroke: color },
      labelStyle: { fill: '#4338CA', fontWeight: 700 },
      markerEnd: { type: MarkerType.ArrowClosed, color },
    }
  }

  const outcome = connection.sourceHandle || 'next'
  const color = OUTCOME_COLORS[outcome]
  return {
    ...connection,
    id,
    type: 'adaptive',
    reconnectable: 'target',
    data: { ...connection.data },
    label: outcome === 'next' ? undefined : OUTCOME_LABELS[outcome] || outcome,
    style: color ? { stroke: color } : undefined,
    labelStyle: color ? { fill: color, fontWeight: 700 } : undefined,
    markerEnd: { type: MarkerType.ArrowClosed, color },
  }
}

function withoutTargets(nodes, removedIds) {
  return nodes.map((node) => {
    const buttons = node.data.params?.buttons
    if (!Array.isArray(buttons)) return node
    const nextButtons = buttons.map((button) => (
      button.action === 'next' && removedIds.has(button.target) ? { ...button, target: '' } : button
    ))
    return nextButtons.some((button, index) => button !== buttons[index])
      ? { ...node, data: { ...node.data, params: { ...node.data.params, buttons: nextButtons } } }
      : node
  })
}

function withoutButtonEdgeTargets(nodes, removedEdges) {
  return nodes.map((node) => {
    const buttons = node.data.params?.buttons
    if (!Array.isArray(buttons)) return node
    const nextButtons = buttons.map((button, index) => {
      const removed = removedEdges.some((edge) => (
        edge.source === node.id
        && buttonIndexFromHandle(edge.sourceHandle) === index
        && edge.target === button.target
      ))
      return removed && button.action === 'next' ? { ...button, target: '' } : button
    })
    return nextButtons.some((button, index) => button !== buttons[index])
      ? { ...node, data: { ...node.data, params: { ...node.data.params, buttons: nextButtons } } }
      : node
  })
}

function Editor() {
  const [nodes, setNodes, applyNodeChanges] = useNodesState(initialNodes)
  const [edges, setEdges, applyEdgeChanges] = useEdgesState(initialPresentationEdges)
  const [platform, setPlatform] = useState('telegram')
  const [botName, setBotName] = useState('Новый бот')
  const [selectedId, setSelectedId] = useState(null)
  const [showJson, setShowJson] = useState(false)
  const [problems, setProblems] = useState(null)
  const [paletteOpen, setPaletteOpen] = useState(initialPaletteOpen)
  const [rightOpen, setRightOpen] = useState(false)
  const [rightTab, setRightTab] = useState('settings')
  const [selection, setSelection] = useState({ nodes: [], edges: [] })
  const [clipboardInfo, setClipboardInfo] = useState(null)
  const [graphRevision, setGraphRevision] = useState(0)
  const [savedGraphRevision, setSavedGraphRevision] = useState(null)
  const [savedName, setSavedName] = useState('')
  const [botSession, setBotSession] = useState({
    botId: '',
    connectedBotName: '',
    flowId: '',
    rowVersion: null,
    status: 'draft',
    miniAppAttached: false,
    miniAppUrl: '',
    miniAppTitle: '',
    notificationRole: 'sales',
    notificationChatId: '',
    baseUrl: '',
    busy: null,
    apiStatus: { kind: 'idle', message: '' },
  })
  const graphRef = useRef({ nodes, edges })
  const reconnectingEdgeRef = useRef(null)
  const clipboardRef = useRef(null)
  graphRef.current = { nodes, edges }
  const { screenToFlowPosition, setCenter, deleteElements } = useReactFlow()

  const nodeTypes = useMemo(() => ({ block: BlockNode, trigger: TriggerNode }), [])
  const touchGraph = useCallback(() => {
    setGraphRevision((current) => current + 1)
    setProblems(null)
  }, [])

  const updateEdgeBend = useCallback((edgeId, bend) => {
    setEdges((current) => current.map((edge) => (
      edge.id === edgeId ? { ...edge, data: { ...edge.data, bend } } : edge
    )))
  }, [setEdges])

  const edgeTypes = useMemo(() => ({
    adaptive: (props) => <AdaptiveEdge {...props} onBendChange={updateEdgeBend} />,
  }), [updateEdgeBend])

  const selectedBlockCount = useMemo(
    () => selection.nodes.filter((node) => node.data?.group === 'block').length,
    [selection.nodes],
  )
  const selectedNodeCount = selection.nodes.length
  const selectedEdgeCount = selection.edges.length
  const selectedElementCount = selection.nodes.length + selection.edges.length
  const selectionSummary = useMemo(() => [
    selectedNodeCount > 0 && `${selectedNodeCount} ${plural(selectedNodeCount, ['узел', 'узла', 'узлов'])}`,
    selectedEdgeCount > 0 && `${selectedEdgeCount} ${plural(selectedEdgeCount, ['связь', 'связи', 'связей'])}`,
  ].filter(Boolean).join(' · '), [selectedEdgeCount, selectedNodeCount])

  const clearClipboard = useCallback(() => {
    clipboardRef.current = null
    setClipboardInfo(null)
  }, [])

  const clearSelection = useCallback(() => {
    setNodes((current) => current.map((node) => (node.selected ? { ...node, selected: false } : node)))
    setEdges((current) => current.map((edge) => (edge.selected ? { ...edge, selected: false } : edge)))
    setSelection({ nodes: [], edges: [] })
    setSelectedId(null)
  }, [setEdges, setNodes])

  const clearSelectionContext = useCallback(() => {
    clearSelection()
    clearClipboard()
  }, [clearClipboard, clearSelection])

  const copySelection = useCallback(() => {
    const selectedIds = new Set(selection.nodes.map((node) => node.id))
    const snapshot = createBlockSelectionSnapshot(
      nodes.map((node) => ({ ...node, selected: selectedIds.has(node.id) })),
      edges,
    )
    if (!snapshot) return

    clipboardRef.current = { ...snapshot, pasteCount: 0 }
    setClipboardInfo({ blockCount: snapshot.nodes.length, pasteCount: 0 })
  }, [edges, nodes, selection.nodes])

  const pasteSelection = useCallback(() => {
    const clipboard = clipboardRef.current
    if (!clipboard) return

    const pasteCount = clipboard.pasteCount + 1
    const result = pasteBlockSelectionSnapshot({
      nodes,
      edges,
      snapshot: clipboard,
      createNodeId: newId,
      createEdgeId: newEdgeId,
      offset: { x: 48 * pasteCount, y: 48 * pasteCount },
    })
    if (result.createdNodeIds.length === 0) return

    clipboard.pasteCount = pasteCount
    setNodes(result.nodes)
    setEdges(result.edges)
    setSelection({
      nodes: result.nodes.filter((node) => node.selected),
      edges: result.edges.filter((edge) => edge.selected),
    })
    setClipboardInfo({ blockCount: clipboard.nodes.length, pasteCount })
    setSelectedId(result.createdNodeIds.length === 1 ? result.createdNodeIds[0] : null)
    touchGraph()
  }, [edges, nodes, setEdges, setNodes, touchGraph])

  const selectAllElements = useCallback(() => {
    setNodes((current) => current.map((node) => ({ ...node, selected: true })))
    setEdges((current) => current.map((edge) => ({ ...edge, selected: true })))
    setSelection({ nodes, edges })
    setSelectedId(null)
  }, [edges, nodes, setEdges, setNodes])

  const deleteSelection = useCallback(() => {
    if (selectedElementCount === 0) return
    void deleteElements({ nodes: selection.nodes, edges: selection.edges })
    setSelectedId(null)
  }, [deleteElements, selectedElementCount, selection.edges, selection.nodes])

  useEffect(() => {
    const onKeyDown = (event) => {
      if (isEditableTarget(event.target)) return
      const withPrimaryModifier = event.ctrlKey || event.metaKey
      const key = event.key.toLowerCase()

      if (withPrimaryModifier && key === 'a') {
        event.preventDefault()
        selectAllElements()
      }
      if (withPrimaryModifier && key === 'c' && selectedBlockCount > 0) {
        event.preventDefault()
        copySelection()
      }
      if (withPrimaryModifier && key === 'v' && clipboardRef.current) {
        event.preventDefault()
        pasteSelection()
      }
      if (event.key === 'Escape') clearSelectionContext()
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [clearSelectionContext, copySelection, pasteSelection, selectAllElements, selectedBlockCount])

  const validation = useMemo(
    () => validateFlow(graphRef.current.nodes, graphRef.current.edges, platform),
    // Position changes are deliberately excluded: they do not alter Flow data.
    [graphRevision, platform],
  )
  const publishValidation = useMemo(
    () => validateFlow(graphRef.current.nodes, graphRef.current.edges, platform, {
      requireMiniApp: true,
      miniAppAttached: botSession.miniAppAttached,
    }),
    [graphRevision, platform, botSession.miniAppAttached],
  )
  const nodeErrorCounts = useMemo(() => {
    const counts = new Map()
    for (const problem of publishValidation.problems) {
      if (!problem.nodeId) continue
      counts.set(problem.nodeId, (counts.get(problem.nodeId) || 0) + 1)
    }
    return counts
  }, [publishValidation])
  const displayNodes = useMemo(
    () => nodes.map((node) => ({
      ...node,
      data: { ...node.data, errorCount: nodeErrorCounts.get(node.id) || 0 },
    })),
    [nodeErrorCounts, nodes],
  )

  useEffect(() => {
    setProblems((current) => {
      if (!publishValidation.ok) return publishValidation
      return current?.ok ? current : null
    })
  }, [publishValidation])
  const definition = useMemo(
    () => serializeDefinition(graphRef.current.nodes, graphRef.current.edges),
    [graphRevision],
  )
  const flow = useMemo(
    () => ({ bot: { name: botName, platform }, definition }),
    [botName, definition, platform],
  )

  const selected = useMemo(
    () => nodes.find((node) => node.id === selectedId) || null,
    [nodes, selectedId],
  )
  const isDirty = savedGraphRevision === null || savedGraphRevision !== graphRevision || savedName !== botName
  const platformLocked = Boolean(botSession.botId)
  const editorStatus = useMemo(() => {
    if (botSession.status === 'published' && !isDirty) {
      return { kind: 'ok', text: 'Опубликован', detail: 'Опубликована текущая сохранённая версия сценария' }
    }
    if (!validation.ok) {
      return { kind: 'bad', text: `${validation.problems.length} ${validation.problems.length === 1 ? 'проблема' : 'проблемы'}`, detail: 'Проверьте схему перед сохранением' }
    }
    if (botSession.rowVersion !== null && !isDirty) {
      return { kind: 'ok', text: 'Черновик сохранён', detail: 'Текущая логика сценария сохранена' }
    }
    return { kind: 'warn', text: botSession.botId ? 'Есть изменения' : 'Черновик', detail: 'Подключите бота, затем сохраните сценарий' }
  }, [botSession.botId, botSession.rowVersion, botSession.status, isDirty, validation])

  const isValidConnection = useCallback((connection) => {
    if (!connection.source || !connection.target) return false
    const source = nodes.find((node) => node.id === connection.source)
    if (!source) return false
    const sourceHandle = connection.sourceHandle || 'next'
    const occupiedEdges = edges.filter((edge) => edge.id !== reconnectingEdgeRef.current)
    const buttonIndex = buttonIndexFromHandle(sourceHandle)
    if (buttonIndex !== null) {
      const button = source.data.params?.buttons?.[buttonIndex]
      return button?.action === 'next' && !occupiedEdges.some((edge) => (
        edge.source === connection.source && edge.sourceHandle === sourceHandle
      ))
    }
    if (source.data.group === 'trigger') {
      return !occupiedEdges.some((edge) => edge.source === connection.source)
    }
    const outputs = BLOCK_BY_TYPE[source.data.type]?.outputs || []
    return outputs.includes(sourceHandle) && !occupiedEdges.some((edge) => (
      edge.source === connection.source && (edge.sourceHandle || 'next') === sourceHandle
    ))
  }, [edges, nodes])

  const onSelectionChange = useCallback(({ nodes: nextNodes, edges: nextEdges }) => {
    setSelection({ nodes: nextNodes, edges: nextEdges })
    setSelectedId(nextNodes.length === 1 ? nextNodes[0].id : null)
    if (nextNodes.length + nextEdges.length === 0) clearClipboard()
  }, [clearClipboard])

  const onReconnectStart = useCallback((_, edge) => {
    reconnectingEdgeRef.current = edge.id
  }, [])

  const onReconnectEnd = useCallback(() => {
    reconnectingEdgeRef.current = null
  }, [])

  const onReconnect = useCallback((oldEdge, connection) => {
    if (!connection.source || !connection.target) return
    const unchanged = oldEdge.source === connection.source
      && oldEdge.target === connection.target
      && (oldEdge.sourceHandle || null) === (connection.sourceHandle || null)
      && (oldEdge.targetHandle || null) === (connection.targetHandle || null)
    if (unchanged) return

    const buttonIndex = buttonIndexFromHandle(oldEdge.sourceHandle)
    if (buttonIndex !== null) {
      setNodes((current) => current.map((node) => {
        if (node.id !== oldEdge.source) return node
        const buttons = node.data.params?.buttons || []
        const nextButtons = buttons.map((button, index) => (
          index === buttonIndex ? { ...button, target: connection.target } : button
        ))
        return { ...node, data: { ...node.data, params: { ...node.data.params, buttons: nextButtons } } }
      }))
    }

    setEdges((current) => reconnectEdge(oldEdge, connection, current, { shouldReplaceId: false }).map((edge) => (
      edge.id === oldEdge.id
        ? { ...edge, type: 'adaptive', reconnectable: 'target', data: { ...edge.data, bend: undefined } }
        : edge
    )))
    touchGraph()
  }, [setEdges, setNodes, touchGraph])

  const onConnect = useCallback((connection) => {
    const buttonIndex = buttonIndexFromHandle(connection.sourceHandle)
    if (buttonIndex !== null) {
      setNodes((current) => current.map((node) => {
        if (node.id !== connection.source) return node
        const buttons = node.data.params?.buttons || []
        const nextButtons = buttons.map((button, index) => (
          index === buttonIndex ? { ...button, target: connection.target } : button
        ))
        return { ...node, data: { ...node.data, params: { ...node.data.params, buttons: nextButtons } } }
      }))
      setEdges((current) => {
        const withoutPrevious = current.filter((edge) => !(
          edge.source === connection.source && edge.sourceHandle === connection.sourceHandle
        ))
        return [...withoutPrevious, presentationEdge(connection, nodes)]
      })
    } else {
      setEdges((current) => addEdge(presentationEdge(connection, nodes), current))
    }
    touchGraph()
  }, [nodes, setEdges, setNodes, touchGraph])

  const onNodesChange = useCallback((changes) => {
    applyNodeChanges(changes)
    const removedIds = new Set(changes.filter((change) => change.type === 'remove').map((change) => change.id))
    const graphChanged = changes.some((change) => ['add', 'remove', 'replace', 'reset'].includes(change.type))
    if (removedIds.size > 0) {
      setNodes((current) => withoutTargets(current, removedIds))
      setEdges((current) => current.filter((edge) => !removedIds.has(edge.source) && !removedIds.has(edge.target)))
      if (removedIds.has(selectedId)) setSelectedId(null)
    }
    if (graphChanged) touchGraph()
  }, [applyNodeChanges, selectedId, setEdges, setNodes, touchGraph])

  const onEdgesChange = useCallback((changes) => {
    const removedButtonEdges = changes
      .filter((change) => change.type === 'remove')
      .map((change) => edges.find((edge) => edge.id === change.id))
      .filter((edge) => edge && isButtonEdge(edge))
    applyEdgeChanges(changes)
    if (removedButtonEdges.length > 0) {
      setNodes((current) => withoutButtonEdgeTargets(current, removedButtonEdges))
    }
    if (changes.some((change) => ['add', 'remove', 'replace', 'reset'].includes(change.type))) touchGraph()
  }, [applyEdgeChanges, edges, setNodes, touchGraph])

  const addItem = useCallback((item, group, position) => {
    const id = newId()
    const nextNode = group === 'trigger'
      ? {
          id,
          type: 'trigger',
          position,
          data: { group: 'trigger', type: item.type, label: item.label, icon: item.icon, config: {} },
        }
      : {
          id,
          type: 'block',
          position,
          data: { group: 'block', type: item.type, params: makeDefaultParams(item.type) },
        }
    setNodes((current) => [...current, nextNode])
    setSelectedId(id)
    setRightTab('settings')
    if (isCompactViewport()) setPaletteOpen(false)
    setRightOpen(true)
    touchGraph()
  }, [setNodes, touchGraph])

  const onDragOver = useCallback((event) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback((event) => {
    event.preventDefault()
    const raw = event.dataTransfer.getData('application/mbc')
    if (!raw) return
    try {
      const item = JSON.parse(raw)
      const position = screenToFlowPosition({ x: event.clientX, y: event.clientY })
      addItem(item, item.group, position)
    } catch {
      // Игнорируем данные не из палитры конструктора.
    }
  }, [addItem, screenToFlowPosition])

  const onPaletteAdd = useCallback((item, group) => {
    const position = screenToFlowPosition({
      x: Math.round(window.innerWidth * 0.55),
      y: Math.round(window.innerHeight * 0.55),
    })
    addItem(item, group, position)
  }, [addItem, screenToFlowPosition])

  const syncButtonEdges = useCallback((sourceId, buttons) => {
    const blockIds = new Set(nodes.filter((node) => node.data.group === 'block').map((node) => node.id))
    setEdges((current) => {
      const otherEdges = current.filter((edge) => !(edge.source === sourceId && isButtonEdge(edge)))
      const buttonEdges = buttons.flatMap((button, index) => {
        if (button.action !== 'next' || !blockIds.has(button.target)) return []
        return [presentationEdge({ source: sourceId, sourceHandle: `button:${index}`, target: button.target }, nodes)]
      })
      return [...otherEdges, ...buttonEdges]
    })
  }, [nodes, setEdges])

  const updateParams = useCallback((id, patch) => {
    const currentNode = nodes.find((node) => node.id === id)
    const nextButtons = patch.buttons ?? currentNode?.data.params?.buttons
    setNodes((current) => current.map((node) => (
      node.id === id
        ? { ...node, data: { ...node.data, params: { ...node.data.params, ...patch } } }
        : node
    )))
    if (patch.buttons) syncButtonEdges(id, nextButtons)
    touchGraph()
  }, [nodes, setNodes, syncButtonEdges, touchGraph])

  const updateTriggerConfig = useCallback((id, patch) => {
    setNodes((current) => current.map((node) => (
      node.id === id
        ? { ...node, data: { ...node.data, config: { ...(node.data.config || {}), ...patch } } }
        : node
    )))
    touchGraph()
  }, [setNodes, touchGraph])

  const deleteNode = useCallback((id) => {
    const removedIds = new Set([id])
    setNodes((current) => withoutTargets(current, removedIds).filter((node) => node.id !== id))
    setEdges((current) => current.filter((edge) => edge.source !== id && edge.target !== id))
    setSelectedId(null)
    touchGraph()
  }, [setEdges, setNodes, touchGraph])

  const focusProblem = useCallback((problem) => {
    if (!problem?.nodeId) return
    const node = nodes.find((item) => item.id === problem.nodeId)
    if (!node) return
    const focusedNode = { ...node, selected: true }
    setNodes((current) => current.map((item) => ({ ...item, selected: item.id === node.id })))
    setEdges((current) => current.map((edge) => (
      edge.selected ? { ...edge, selected: false } : edge
    )))
    setSelection({ nodes: [focusedNode], edges: [] })
    setSelectedId(node.id)
    setRightTab('settings')
    if (isCompactViewport()) setPaletteOpen(false)
    setRightOpen(true)
    setCenter(node.position.x + 110, node.position.y + 60, { zoom: 1.1, duration: 250 })
  }, [nodes, setCenter, setEdges, setNodes])

  const onCheck = useCallback(() => {
    setProblems(publishValidation)
    const firstNodeProblem = publishValidation.problems.find((problem) => problem.nodeId)
    if (!publishValidation.ok && firstNodeProblem) focusProblem(firstNodeProblem)
  }, [focusProblem, publishValidation])

  const openPublish = useCallback(() => {
    if (!publishValidation.ok) setProblems(publishValidation)
    setRightTab('publish')
    if (isCompactViewport()) setPaletteOpen(false)
    setRightOpen(true)
  }, [publishValidation])

  const togglePalette = useCallback(() => {
    const nextOpen = !paletteOpen
    setPaletteOpen(nextOpen)
    if (nextOpen && isCompactViewport()) setRightOpen(false)
  }, [paletteOpen])

  const toggleRight = useCallback(() => {
    const nextOpen = !rightOpen
    setRightOpen(nextOpen)
    if (nextOpen && isCompactViewport()) setPaletteOpen(false)
  }, [rightOpen])

  const onConnected = useCallback((bot) => {
    setPlatform(bot.platform)
    setBotName(bot.name)
    setBotSession((current) => ({
      ...current,
      botId: bot.id,
      flowId: bot.flow_id || '',
      rowVersion: null,
      status: bot.status,
      miniAppAttached: false,
    }))
    setSavedGraphRevision(null)
    setSavedName('')
  }, [])

  const onSaved = useCallback((saved) => {
    setBotSession((current) => ({ ...current, flowId: saved.flow_id, rowVersion: saved.row_version, status: 'draft' }))
    setSavedGraphRevision(graphRevision)
    setSavedName(botName)
  }, [botName, graphRevision])

  const onPublished = useCallback((bot) => {
    setBotSession((current) => ({ ...current, status: bot.status }))
  }, [])

  return (
    <div className="app">
      <TopBar
        botName={botName}
        setBotName={setBotName}
        platform={platform}
        setPlatform={setPlatform}
        platformLocked={platformLocked}
        status={editorStatus}
        showJson={showJson}
        setShowJson={setShowJson}
        onCheck={onCheck}
        onOpenPublish={openPublish}
        paletteOpen={paletteOpen}
        onTogglePalette={togglePalette}
        rightOpen={rightOpen}
        onToggleRight={toggleRight}
      />

      <div className={`workspace ${!paletteOpen ? 'workspace--noPalette' : ''} ${!rightOpen ? 'workspace--noRight' : ''}`}>
        {paletteOpen && (
          <div className="leftRail">
            <div className="railHead">
              <span>Добавить в сценарий</span>
              <button className="icon-btn" type="button" onClick={() => setPaletteOpen(false)} aria-label="Закрыть палитру">✕</button>
            </div>
            <Palette platform={platform} onAdd={onPaletteAdd} />
          </div>
        )}

        <div className="canvas" onDrop={onDrop} onDragOver={onDragOver}>
          <ReactFlow
            nodes={displayNodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            isValidConnection={isValidConnection}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            onReconnect={onReconnect}
            onReconnectStart={onReconnectStart}
            onReconnectEnd={onReconnectEnd}
            edgesReconnectable
            reconnectRadius={18}
            selectionOnDrag
            selectionMode={SelectionMode.Partial}
            selectionKeyCode="Shift"
            multiSelectionKeyCode={['Control', 'Meta']}
            panOnDrag={[1]}
            panActivationKeyCode="Space"
            autoPanOnSelection
            deleteKeyCode={['Backspace', 'Delete']}
            onSelectionChange={onSelectionChange}
            onNodeClick={(event, node) => {
              if (event.ctrlKey || event.metaKey || event.shiftKey) return
              setSelectedId(node.id)
              setRightTab('settings')
              if (isCompactViewport()) setPaletteOpen(false)
              setRightOpen(true)
            }}
            onPaneClick={clearSelectionContext}
            fitView
            fitViewOptions={{ padding: 0.24 }}
            aria-label="Схема сценария бота"
          >
            <Background gap={16} color="#dbe2ea" />
            <Controls />
            <MiniMap pannable zoomable nodeStrokeWidth={2} />
          </ReactFlow>

          {(selectedElementCount > 0 || clipboardInfo) && (
            <div className="selectionToolbar" role="toolbar" aria-label="Действия с выделенными элементами">
              <div className="selectionToolbar__status" aria-live="polite" title="Рамка выделяет и узлы, и связи. Ctrl/⌘ + клик добавляет элемент к выделению.">
                {selectedElementCount > 0
                  ? `Выбрано: ${selectionSummary}`
                  : `Буфер: ${clipboardInfo.blockCount} блок.`}
              </div>
              <button
                className="selectionToolbar__btn"
                type="button"
                onClick={copySelection}
                disabled={selectedBlockCount === 0}
                title="Копировать выбранные блоки (Ctrl/Cmd+C)"
              >
                Копировать
              </button>
              <button
                className="selectionToolbar__btn"
                type="button"
                onClick={pasteSelection}
                disabled={!clipboardInfo}
                title="Вставить копию блоков (Ctrl/Cmd+V)"
              >
                Вставить
              </button>
              <button
                className="selectionToolbar__btn selectionToolbar__btn--danger"
                type="button"
                onClick={deleteSelection}
                disabled={selectedElementCount === 0}
                title="Удалить выделенное (Delete / Backspace)"
              >
                Удалить
              </button>
              <button
                className="icon-btn"
                type="button"
                onClick={clearSelectionContext}
                aria-label={selectedElementCount > 0 ? 'Снять выделение и очистить буфер' : 'Очистить буфер'}
                title={selectedElementCount > 0 ? 'Снять выделение и очистить буфер (Esc)' : 'Очистить буфер (Esc)'}
              >
                ✕
              </button>
            </div>
          )}

          {problems && (
            <div
              className={`dock ${problems.ok ? 'dock--ok' : 'dock--bad'}`}
              role={problems.ok ? 'status' : 'alert'}
              aria-live={problems.ok ? 'polite' : 'assertive'}
            >
              {problems.ok ? (
                <span>Сценарий проходит локальную проверку. Его можно сохранить и подготовить к публикации.</span>
              ) : (
                <div className="dock__content">
                  <strong>Исправьте перед публикацией:</strong>
                  {problems.problems.map((problem, index) => (
                    problem.nodeId ? (
                      <button className="dock__problem" type="button" key={`${problem.message}-${index}`} onClick={() => focusProblem(problem)}>
                        {problem.message}
                      </button>
                    ) : (
                      <span className="dock__problem dock__problem--static" key={`${problem.message}-${index}`}>{problem.message}</span>
                    )
                  ))}
                </div>
              )}
              <button className="icon-btn" type="button" onClick={() => setProblems(null)} aria-label="Закрыть результаты проверки">✕</button>
            </div>
          )}
        </div>

        {rightOpen && (
          <div className="rightRail">
            <div className="rightRail__head">
              <div className="tabs" role="tablist" aria-label="Правая панель">
                <button type="button" role="tab" className={`tab ${rightTab === 'settings' ? 'tab--on' : ''}`} onClick={() => setRightTab('settings')} aria-selected={rightTab === 'settings'}>
                  Настройки
                </button>
                <button type="button" role="tab" className={`tab ${rightTab === 'publish' ? 'tab--on' : ''}`} onClick={openPublish} aria-selected={rightTab === 'publish'}>
                  Публикация
                </button>
              </div>
              <button className="icon-btn" type="button" onClick={() => setRightOpen(false)} aria-label="Закрыть панель">✕</button>
            </div>
            {rightTab === 'settings' ? (
              <ConfigPanel
                node={selected}
                nodes={nodes}
                onParamsChange={updateParams}
                onConfigChange={updateTriggerConfig}
                onDelete={deleteNode}
              />
            ) : (
              <ApiPanel
                flow={flow}
                validation={validation}
                publishValidation={publishValidation}
                botName={botName}
                platform={platform}
                session={botSession}
                onSessionChange={setBotSession}
                onConnected={onConnected}
                onSaved={onSaved}
                onPublished={onPublished}
                isDirty={isDirty}
                onCheck={onCheck}
              />
            )}
          </div>
        )}
      </div>

      {(paletteOpen || rightOpen) && (
        <button className="drawerScrim" type="button" onClick={() => { setPaletteOpen(false); setRightOpen(false) }} aria-label="Закрыть панели" />
      )}

      {showJson && <JsonDrawer flow={flow} onClose={() => setShowJson(false)} />}
    </div>
  )
}

export default function App() {
  return (
    <ReactFlowProvider>
      <Editor />
    </ReactFlowProvider>
  )
}
