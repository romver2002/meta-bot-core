import { Handle, Position } from '@xyflow/react'

function summary(data) {
  if (data.type === 'text') return data.config?.pattern ? `pattern: ${data.config.pattern}` : 'text trigger'
  if (data.type === 'callback') return data.config?.payload ? `payload: ${data.config.payload}` : 'callback trigger'
  if (data.type === 'mini_app_result') return 'mini app result'
  return 'Вход в сценарий'
}

// Триггер — точка входа в сценарий. Только исходящий порт (без target).
export default function TriggerNode({ data, selected }) {
  return (
    <div className={`node node--trigger ${selected ? 'node--selected' : ''}`}>
      <div className="node__head">
        <span className="node__icon">{data.icon}</span>
        <span className="node__title">{data.label}</span>
      </div>
      <div className="node__summary">{summary(data)}</div>
      <Handle id="next" type="source" position={Position.Bottom} className="handle handle--trigger" />
    </div>
  )
}
