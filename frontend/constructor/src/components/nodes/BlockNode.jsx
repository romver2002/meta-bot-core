import { memo, useEffect, useMemo } from 'react'
import { Handle, Position, useUpdateNodeInternals } from '@xyflow/react'

import { BLOCK_BY_TYPE, OUTCOME_LABELS } from '../../domain/catalog.js'
import { buttonHandleId } from '../../flow/handles.js'

function summary(type, params = {}) {
  switch (type) {
    case 'send_message': return params.text || '—'
    case 'show_buttons': return `${params.text || '—'} · ${(params.buttons || []).length} кноп.`
    case 'ask': return `${params.prompt || '—'} → {${params.save_as || '?'}}`
    case 'condition': return params.expression || '—'
    case 'open_mini_app': return params.button_text ? `кнопка: ${params.button_text}` : 'настройте кнопку запуска'
    case 'save': return `${params.key || '?'} = ${params.value || ''}`
    case 'http_request': return `${params.method || 'GET'} ${params.url || '—'}`
    case 'notify': return `роль: ${params.to || '—'}`
    case 'custom_code': return 'Python · песочница'
    default: return ''
  }
}

function BlockNode({ id, data, selected }) {
  const def = BLOCK_BY_TYPE[data.type]
  const updateNodeInternals = useUpdateNodeInternals()
  const buttons = Array.isArray(data.params?.buttons) ? data.params.buttons : []
  const errorCount = Number(data.errorCount || 0)
  const nextButtons = useMemo(
    () => buttons.map((button, index) => ({ button, index })).filter(({ button }) => button.action === 'next'),
    [buttons],
  )
  const buttonSignature = nextButtons.map(({ button, index }) => `${index}:${button.label}:${button.target}`).join('|')

  useEffect(() => {
    updateNodeInternals(id)
  }, [buttonSignature, id, updateNodeInternals])

  if (!def) {
    return <div className="node node--unknown">Неизвестный блок</div>
  }

  const outputs = def.outputs || []
  return (
    <div
      className={`node ${selected ? 'node--selected' : ''} ${errorCount > 0 ? 'node--invalid' : ''}`}
      style={{ '--accent': def.color }}
    >
      <Handle type="target" position={Position.Top} className="handle" />
      <div className="node__head">
        <span className="node__icon">{def.icon}</span>
        <span className="node__title">{def.label}</span>
        {errorCount > 0 && <span className="node__error" title={`Ошибок: ${errorCount}`} aria-label={`Ошибок в блоке: ${errorCount}`}>⚠</span>}
        {def.sandbox && <span className="node__badge" title="Изолированная песочница (BR-004)">🔒</span>}
      </div>
      <div className="node__summary">{summary(data.type, data.params)}</div>

      {nextButtons.length > 0 && (
        <div className="node__choices" aria-label="Переходы по кнопкам">
          {nextButtons.map(({ button, index }) => (
            <div className="node__choice" key={buttonHandleId(index)}>
              <span>{button.label || `Кнопка ${index + 1}`}</span>
              <Handle
                id={buttonHandleId(index)}
                type="source"
                position={Position.Right}
                className="handle handle--button"
              />
            </div>
          ))}
        </div>
      )}

      {outputs.length > 0 && (
        <div className={`node__branches node__branches--${outputs.length}`}>
          {outputs.map((outcome) => (
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

export default memo(BlockNode)
