import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'

function summary(data) {
  if (data.type === 'text') return data.config?.pattern ? `pattern: ${data.config.pattern}` : 'text trigger'
  if (data.type === 'callback') return data.config?.payload ? `payload: ${data.config.payload}` : 'callback trigger'
  if (data.type === 'mini_app_result') return 'mini app result'
  return 'Вход в сценарий'
}

// Триггер — точка входа в сценарий. Только исходящий порт (без target).
function TriggerNode({ data, selected }) {
  const errorCount = Number(data.errorCount || 0)
  return (
    <div className={`node node--trigger ${selected ? 'node--selected' : ''} ${errorCount > 0 ? 'node--invalid' : ''}`}>
      <div className="node__head">
        <span className="node__icon">{data.icon}</span>
        <span className="node__title">{data.label}</span>
        {errorCount > 0 && <span className="node__error" title={`Ошибок: ${errorCount}`} aria-label={`Ошибок во входе: ${errorCount}`}>⚠</span>}
      </div>
      <div className="node__summary">{summary(data)}</div>
      <Handle id="next" type="source" position={Position.Bottom} className="handle handle--trigger" />
    </div>
  )
}

export default memo(TriggerNode)
