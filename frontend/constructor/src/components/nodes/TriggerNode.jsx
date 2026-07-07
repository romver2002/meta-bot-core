import { Handle, Position } from '@xyflow/react'

// Триггер — точка входа в сценарий. Только исходящий порт (без target).
export default function TriggerNode({ data, selected }) {
  return (
    <div className={`node node--trigger ${selected ? 'node--selected' : ''}`}>
      <div className="node__head">
        <span className="node__icon">{data.icon}</span>
        <span className="node__title">{data.label}</span>
      </div>
      <div className="node__summary">Вход в сценарий</div>
      <Handle id="next" type="source" position={Position.Bottom} className="handle handle--trigger" />
    </div>
  )
}
