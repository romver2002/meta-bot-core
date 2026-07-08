import { Handle, Position } from '@xyflow/react'
import { BLOCK_BY_TYPE, OUTCOME_LABELS } from '../../domain/catalog.js'

// Короткая сводка параметров блока для карточки на холсте.
function summary(type, params = {}) {
  switch (type) {
    case 'send_message': return params.text || '—'
    case 'show_buttons': return `${params.text || ''} · ${(params.buttons || []).length} кноп.`
    case 'ask': return `${params.prompt || '—'}  →  {${params.save_as || '?'}}`
    case 'condition': return params.expression || '—'
    case 'open_mini_app': return params.button_text ? `кнопка: ${params.button_text}` : 'mini app через API конструктора'
    case 'save': return `${params.key || '?'} = ${params.value || ''}`
    case 'http_request': return `${params.method || 'GET'} ${params.url || '—'}`
    case 'custom_code': return 'Python · песочница'
    default: return ''
  }
}

export default function BlockNode({ data, selected }) {
  const def = BLOCK_BY_TYPE[data.type]
  const outputs = def.outputs || []
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

      {outputs.length > 0 && (
        <div className={`node__branches node__branches--${outputs.length}`}>
          {outputs.map((outcome, index) => (
            <span key={outcome} className={`br br--${outcome}`}>{OUTCOME_LABELS[outcome] || outcome}</span>
          ))}
        </div>
      )}
      {outputs.map((outcome, index) => (
        <Handle
          key={outcome}
          id={outcome}
          type="source"
          position={Position.Bottom}
          className={`handle handle--${outcome}`}
          style={{ left: `${((index + 1) / (outputs.length + 1)) * 100}%` }}
        />
      ))}
    </div>
  )
}
