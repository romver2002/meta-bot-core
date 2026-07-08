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
import ApiPanel from './components/ApiPanel.jsx'
import { initialNodes, initialEdges } from './flow/initialFlow.js'
import { serializeFlow, validateFlow } from './flow/serialize.js'
import { OUTCOME_LABELS, makeDefaultParams } from './domain/catalog.js'

let counter = 100
const newId = () => `n${counter++}`
const initialPaletteOpen = () => (typeof window === 'undefined' ? true : window.innerWidth > 900)

function Editor() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)
  const [platform, setPlatform] = useState('telegram')
  const [botName, setBotName] = useState('Умный помощник по заявкам')
  const [selectedId, setSelectedId] = useState(null)
  const [showJson, setShowJson] = useState(false)
  const [problems, setProblems] = useState(null)
  const [paletteOpen, setPaletteOpen] = useState(initialPaletteOpen)
  const [rightOpen, setRightOpen] = useState(false)
  const [rightTab, setRightTab] = useState('settings')
  const { screenToFlowPosition } = useReactFlow()

  const nodeTypes = useMemo(() => ({ block: BlockNode, trigger: TriggerNode }), [])

  const onConnect = useCallback((c) => {
    const colors = { true: '#16A34A', false: '#64748B', error: '#DC2626' }
    const color = colors[c.sourceHandle]
    setEdges((eds) => addEdge({
      ...c,
      label: OUTCOME_LABELS[c.sourceHandle] || undefined,
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
        data: { group: 'trigger', type: item.type, label: item.label, icon: item.icon, config: {} } }])
    } else {
      const params = makeDefaultParams(item.type)
      setNodes((nds) => [...nds, { id, type: 'block', position, data: { group: 'block', type: item.type, params } }])
    }
    setSelectedId(id)
    setRightTab('settings')
    setRightOpen(true)
  }, [screenToFlowPosition, setNodes])

  const onNodeClick = useCallback((_, n) => {
    setSelectedId(n.id)
    setRightTab('settings')
    setRightOpen(true)
  }, [])
  const onPaneClick = useCallback(() => setSelectedId(null), [])

  const updateParams = useCallback((id, patch) => {
    setNodes((nds) => nds.map((n) => (n.id === id
      ? { ...n, data: { ...n.data, params: { ...n.data.params, ...patch } } } : n)))
  }, [setNodes])

  const updateTriggerConfig = useCallback((id, patch) => {
    setNodes((nds) => nds.map((n) => (n.id === id
      ? { ...n, data: { ...n.data, config: { ...(n.data.config || {}), ...patch } } } : n)))
  }, [setNodes])

  const deleteNode = useCallback((id) => {
    setNodes((nds) => nds.filter((n) => n.id !== id))
    setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id))
    setSelectedId(null)
  }, [setNodes, setEdges])

  const selected = nodes.find((n) => n.id === selectedId) || null
  const validation = validateFlow(nodes, edges, platform)
  const flow = serializeFlow(nodes, edges, { botName, platform })

  const onCheck = () => setProblems(validation)
  const openPublish = () => {
    setRightTab('publish')
    setRightOpen(true)
  }

  return (
    <div className="app">
      <TopBar
        botName={botName} setBotName={setBotName}
        platform={platform} setPlatform={setPlatform}
        validation={validation} showJson={showJson} setShowJson={setShowJson}
        onCheck={onCheck}
        paletteOpen={paletteOpen} setPaletteOpen={setPaletteOpen}
        rightOpen={rightOpen} setRightOpen={setRightOpen}
      />

      <div className={`workspace ${!paletteOpen ? 'workspace--noPalette' : ''} ${!rightOpen ? 'workspace--noRight' : ''}`}>
        {paletteOpen && (
          <div className="leftRail">
            <div className="railHead">
              <span>Блоки</span>
              <button className="icon-btn" onClick={() => setPaletteOpen(false)} title="Закрыть палитру">✕</button>
            </div>
            <Palette platform={platform} />
          </div>
        )}

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

        {rightOpen && (
          <div className="rightRail">
            <div className="rightRail__head">
              <div className="tabs">
                <button className={`tab ${rightTab === 'settings' ? 'tab--on' : ''}`} onClick={() => setRightTab('settings')}>
                  Настройки
                </button>
                <button className={`tab ${rightTab === 'publish' ? 'tab--on' : ''}`} onClick={openPublish}>
                  Публикация
                </button>
              </div>
              <button className="icon-btn" onClick={() => setRightOpen(false)} title="Закрыть панель">✕</button>
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
              <ApiPanel flow={flow} validation={validation} botName={botName} platform={platform} />
            )}
          </div>
        )}
      </div>

      {(paletteOpen || rightOpen) && (
        <button className="drawerScrim" onClick={() => { setPaletteOpen(false); setRightOpen(false) }} aria-label="Закрыть панели" />
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
