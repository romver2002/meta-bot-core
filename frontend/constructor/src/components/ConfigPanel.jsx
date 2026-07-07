import { BLOCK_BY_TYPE } from '../domain/catalog.js'

// Редактор списка кнопок для блока show_buttons.
function ButtonsField({ value = [], onChange }) {
  const items = Array.isArray(value) ? value : []
  const patch = (i, key, v) => onChange(items.map((b, idx) => (idx === i ? { ...b, [key]: v } : b)))
  const add = () => onChange([...items, { label: 'Кнопка', action: 'next' }])
  const del = (i) => onChange(items.filter((_, idx) => idx !== i))
  return (
    <div className="btnsField">
      {items.map((b, i) => (
        <div className="btnsField__row" key={i}>
          <input value={b.label} onChange={(e) => patch(i, 'label', e.target.value)} placeholder="Подпись" />
          <select value={b.action} onChange={(e) => patch(i, 'action', e.target.value)}>
            <option value="next">→ следующий шаг</option>
            <option value="callback">callback</option>
            <option value="open_mini_app">открыть mini app</option>
            <option value="url">внешняя ссылка</option>
          </select>
          <button className="icon-btn" onClick={() => del(i)} title="Удалить кнопку">✕</button>
        </div>
      ))}
      <button className="btn btn--ghost" onClick={add}>+ кнопка</button>
    </div>
  )
}

function Field({ field, value, onChange }) {
  const common = { value: value ?? '', onChange: (e) => onChange(e.target.value), placeholder: field.placeholder }
  return (
    <label className="field">
      <span className="field__label">{field.label}</span>
      {field.kind === 'textarea' && <textarea rows={3} {...common} />}
      {field.kind === 'text' && <input type="text" {...common} />}
      {field.kind === 'code' && <textarea className="field__code" rows={6} spellCheck={false} {...common} />}
      {field.kind === 'select' && (
        <select {...common}>
          {field.options.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
        </select>
      )}
      {field.kind === 'buttons' && <ButtonsField value={value} onChange={onChange} />}
    </label>
  )
}

export default function ConfigPanel({ node, onChange, onDelete }) {
  if (!node) {
    return (
      <aside className="config config--empty">
        <div className="config__empty">
          <div className="config__empty-ic">⚙️</div>
          Выберите блок на холсте,<br />чтобы настроить его параметры
        </div>
      </aside>
    )
  }

  if (node.data.group === 'trigger') {
    return (
      <aside className="config">
        <div className="config__title"><span>{node.data.icon}</span>{node.data.label}</div>
        <p className="config__hint">Триггер — точка входа в сценарий. Для «Пользователь написал…» здесь задаётся паттерн, для «Нажал кнопку» — payload.</p>
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
        <div className="config__badge">🔒 Исполняется в изолированной песочнице: чистая функция <code>run(context)→dict</code>, без доступа к ФС, сети, токенам и БД (BR-004).</div>
      )}
      {(def.fields || []).map((f) => (
        <Field key={f.key} field={f} value={node.data.params[f.key]}
          onChange={(v) => onChange(node.id, { [f.key]: v })} />
      ))}
      <button className="btn btn--danger" onClick={() => onDelete(node.id)}>Удалить блок</button>
    </aside>
  )
}
