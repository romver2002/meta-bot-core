import { useCallback, useMemo, useState } from 'react'
import {
  ReactFlow, ReactFlowProvider, Background, Controls, MiniMap,
  addEdge, useNodesState, useEdgesState, useReactFlow, MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import BlockNode from './components/nodes/BlockNode.jsx'
import TriggerNode from './components/nodes/TriggerNode.jsx'
import Palette from './components/Palette.jsx'
import ConfigPanel from './components/ConfigPanel.jsx'
import TopBar from './components/TopBar.jsx'
import JsonDrawer from './components/JsonDrawer.jsx'
import { initialNodes, initialEdges } from './flow/initialFlow.js'
import { serializeFlow, validateFlow } from './flow/serialize.js'
import { BLOCK_BY_TYPE } from './domain/catalog.js'

let counter = 100
const newId = () => `n${counter++}`

function Editor() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)
  const [platform, setPlatform] = useState('telegram')
  const [botName, setBotName] = useState('Кофейня Bot')
  const [selectedId, setSelectedId] = useState(null)
  const [showJson, setShowJson] = useState(false)
  const [problems, setProblems] = useState(null)
  const { screenToFlowPosition } = useReactFlow()

  const nodeTypes = useMemo(() => ({ block: BlockNode, trigger: TriggerNode }), [])

  const onConnect = useCallback((c) => {
    const isYes = c.sourceHandle === 'true'
    const isNo = c.sourceHandle === 'false'
    const color = isYes ? '#16A34A' : isNo ? '#64748B' : undefined
    setEdges((eds) => addEdge({
      ...c,
      label: isYes ? 'да' : isNo ? 'нет' : undefined,
      style: color ? { stroke: color } : undefined,
      markerEnd: { type: MarkerType.ArrowClosed, color },
    }, eds))
  }, [setEdges])

  const onDragOver = useCallback((e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move' }, [])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    const raw = e.dataTransfer.getData('application/mbc')
    if (!raw) return
    const item = JSON.parse(raw)
    const position = screenToFlowPosition({ x: e.clientX, y: e.clientY })
    const id = newId()
    if (item.group === 'trigger') {
      setNodes((nds) => [...nds, { id, type: 'trigger', position,
        data: { group: 'trigger', type: item.type, label: item.label, icon: item.icon } }])
    } else {
      const def = BLOCK_BY_TYPE[item.type]
      const params = Object.fromEntries((def.fields || []).map((f) => [f.key, f.kind === 'buttons' ? [] : '']))
      setNodes((nds) => [...nds, { id, type: 'block', position, data: { group: 'block', type: item.type, params } }])
    }
    setSelectedId(id)
  }, [screenToFlowPosition, setNodes])

  const onNodeClick = useCallback((_, n) => setSelectedId(n.id), [])
  const onPaneClick = useCallback(() => setSelectedId(null), [])

  const updateParams = useCallback((id, patch) => {
    setNodes((nds) => nds.map((n) => (n.id === id
      ? { ...n, data: { ...n.data, params: { ...n.data.params, ...patch } } } : n)))
  }, [setNodes])

  const deleteNode = useCallback((id) => {
    setNodes((nds) => nds.filter((n) => n.id !== id))
    setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id))
    setSelectedId(null)
  }, [setNodes, setEdges])

  const selected = nodes.find((n) => n.id === selectedId) || null
  const validation = validateFlow(nodes)
  const flow = serializeFlow(nodes, edges, { botName, platform })

  const onCheck = () => setProblems(validation)

  return (
    <div className="app">
      <TopBar
        botName={botName} setBotName={setBotName}
        platform={platform} setPlatform={setPlatform}
        validation={validation} showJson={showJson} setShowJson={setShowJson}
        onCheck={onCheck}
      />

      <div className="workspace">
        <Palette platform={platform} />

        <div className="canvas" onDrop={onDrop} onDragOver={onDragOver}>
          <ReactFlow
            nodes={nodes} edges={edges}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
            onConnect={onConnect} nodeTypes={nodeTypes}
            onNodeClick={onNodeClick} onPaneClick={onPaneClick}
            fitView
          >
            <Background gap={16} color="#dbe2ea" />
            <Controls />
            <MiniMap pannable zoomable nodeStrokeWidth={2} />
          </ReactFlow>

          {problems && (
            <div className={`dock ${problems.ok ? 'dock--ok' : 'dock--bad'}`}>
              {problems.ok
                ? '✓ Сценарий проходит проверку — можно публиковать (BR-001).'
                : <>⚠ Нельзя опубликовать: {problems.problems.join('; ')}.</>}
              <button className="icon-btn" onClick={() => setProblems(null)}>✕</button>
            </div>
          )}
        </div>

        <ConfigPanel node={selected} onChange={updateParams} onDelete={deleteNode} />
      </div>

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
