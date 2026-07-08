import { BLOCK_BY_TYPE, TRIGGER_BY_TYPE } from '../domain/catalog.js'

function Field({ field, value, onChange }) {
  const common = {
    value: value ?? '',
    onChange: (event) => onChange(event.target.value),
    placeholder: field.placeholder,
  }
  return (
    <label className="field">
      <span className="field__label">{field.label}</span>
      {field.kind === 'textarea' && <textarea rows={3} {...common} />}
      {field.kind === 'text' && <input type="text" {...common} />}
      {field.kind === 'number' && <input type="number" min={field.min} max={field.max} {...common} />}
      {field.kind === 'json' && <textarea className="field__code" rows={7} spellCheck={false} {...common} />}
      {field.kind === 'code' && <textarea className="field__code" rows={6} spellCheck={false} {...common} />}
      {field.kind === 'select' && (
        <select {...common}>
          {field.options.map((option) => <option key={option.v} value={option.v}>{option.l}</option>)}
        </select>
      )}
    </label>
  )
}

function targetLabel(node) {
  const def = BLOCK_BY_TYPE[node.data.type]
  return `${node.id} · ${def?.label || node.data.type}`
}

function ButtonsField({ value = [], onChange, nodes, ownerId }) {
  const items = Array.isArray(value) ? value : []
  const nodeOptions = nodes.filter((node) => node.data.group === 'block' && node.id !== ownerId)
  const patch = (index, key, nextValue) => {
    onChange(items.map((button, current) => (current === index ? { ...button, [key]: nextValue } : button)))
  }
  const add = () => onChange([...items, { label: 'Кнопка', action: 'next', target: '' }])
  const del = (index) => onChange(items.filter((_, current) => current !== index))

  return (
    <div className="btnsField">
      {items.map((button, index) => (
        <div className="btnsField__item" key={index}>
          <div className="btnsField__row">
            <input value={button.label ?? ''} onChange={(event) => patch(index, 'label', event.target.value)} placeholder="Подпись" />
            <select value={button.action ?? 'next'} onChange={(event) => patch(index, 'action', event.target.value)}>
              <option value="next">next → node</option>
              <option value="callback">callback payload</option>
              <option value="open_mini_app">open mini app URL</option>
              <option value="url">external URL</option>
            </select>
            <button className="icon-btn" onClick={() => del(index)} title="Удалить кнопку">✕</button>
          </div>

          {button.action === 'next' ? (
            <select className="btnsField__target" value={button.target ?? ''} onChange={(event) => patch(index, 'target', event.target.value)}>
              <option value="">— target node —</option>
              {nodeOptions.map((node) => <option key={node.id} value={node.id}>{targetLabel(node)}</option>)}
            </select>
          ) : (
            <input
              className="btnsField__target"
              value={button.target ?? ''}
              onChange={(event) => patch(index, 'target', event.target.value)}
              placeholder={button.action === 'url' || button.action === 'open_mini_app' ? 'https://...' : 'payload'}
            />
          )}
        </div>
      ))}
      <button className="btn btn--ghost" onClick={add}>+ кнопка</button>
    </div>
  )
}

export default function ConfigPanel({ node, nodes, onParamsChange, onConfigChange, onDelete }) {
  if (!node) {
    return (
      <aside className="config config--empty">
        <div className="config__empty">
          <div className="config__empty-ic">⚙</div>
          Выберите блок или триггер,<br />чтобы настроить параметры
        </div>
      </aside>
    )
  }

  if (node.data.group === 'trigger') {
    const def = TRIGGER_BY_TYPE[node.data.type]
    return (
      <aside className="config">
        <div className="config__title"><span>{def.icon}</span>{def.label}</div>
        <p className="config__hint">{def.hint}</p>
        {(def.configFields || []).map((field) => (
          <Field
            key={field.key}
            field={field}
            value={node.data.config?.[field.key]}
            onChange={(value) => onConfigChange(node.id, { [field.key]: value })}
          />
        ))}
        <button className="btn btn--danger" onClick={() => onDelete(node.id)}>Удалить триггер</button>
      </aside>
    )
  }

  const def = BLOCK_BY_TYPE[node.data.type]
  return (
    <aside className="config">
      <div className="config__title" style={{ '--accent': def.color }}>
        <span>{def.icon}</span>{def.label}
      </div>
      <p className="config__hint">{def.hint}</p>
      {def.sandbox && (
        <div className="config__badge">
          Исполняется только через будущий sandbox: чистая функция <code>run(context)→dict</code>, без доступа к ФС, сети, токенам и БД.
        </div>
      )}
      {(def.fields || []).map((field) => (
        field.kind === 'buttons' ? (
          <label className="field" key={field.key}>
            <span className="field__label">{field.label}</span>
            <ButtonsField
              value={node.data.params[field.key]}
              nodes={nodes}
              ownerId={node.id}
              onChange={(value) => onParamsChange(node.id, { [field.key]: value })}
            />
          </label>
        ) : (
          <Field
            key={field.key}
            field={field}
            value={node.data.params[field.key]}
            onChange={(value) => onParamsChange(node.id, { [field.key]: value })}
          />
        )
      ))}
      <button className="btn btn--danger" onClick={() => onDelete(node.id)}>Удалить блок</button>
    </aside>
  )
}
