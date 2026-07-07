import { Handle, Position } from '@xyflow/react'
import { BLOCK_BY_TYPE } from '../../domain/catalog.js'

// Короткая сводка параметров блока для карточки на холсте.
function summary(type, params = {}) {
  switch (type) {
    case 'send_message': return params.text || '—'
    case 'show_buttons': return `${params.text || ''} · ${(params.buttons || []).length} кноп.`
    case 'ask': return `${params.prompt || '—'}  →  {${params.save_as || '?'}}`
    case 'condition': return params.expression || '—'
    case 'open_mini_app': return params.mini_app ? `mini app: ${params.mini_app}` : '— выбрать mini app —'
    case 'save': return `${params.key || '?'} = ${params.value || ''}`
    case 'http_request': return `${params.method || 'GET'} ${params.url || '—'}`
    case 'custom_code': return 'Python · песочница'
    default: return ''
  }
}

export default function BlockNode({ data, selected }) {
  const def = BLOCK_BY_TYPE[data.type]
  const isCondition = data.type === 'condition'
  return (
    <div
      className={`node ${selected ? 'node--selected' : ''}`}
      style={{ '--accent': def.color }}
    >
      <Handle type="target" position={Position.Top} className="handle" />
      <div className="node__head">
        <span className="node__icon">{def.icon}</span>
        <span className="node__title">{def.label}</span>
        {def.sandbox && (
          <span className="node__badge" title="Изолированная песочница (BR-004)">🔒</span>
        )}
      </div>
      <div className="node__summary">{summary(data.type, data.params)}</div>

      {isCondition ? (
        <>
          <div className="node__branches"><span className="br br--yes">да</span><span className="br br--no">нет</span></div>
          <Handle id="true" type="source" position={Position.Bottom} className="handle handle--yes" style={{ left: '30%' }} />
          <Handle id="false" type="source" position={Position.Bottom} className="handle handle--no" style={{ left: '70%' }} />
        </>
      ) : (
        <Handle id="next" type="source" position={Position.Bottom} className="handle" />
      )}
    </div>
  )
}
