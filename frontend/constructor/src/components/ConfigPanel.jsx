import { useState } from 'react'

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

function ButtonsField({ value = [], onChange, nodes, ownerId, label }) {
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
            <input value={button.label ?? ''} onChange={(event) => patch(index, 'label', event.target.value)} placeholder="Подпись" aria-label={`${label}: подпись кнопки ${index + 1}`} />
            <select value={button.action ?? 'next'} onChange={(event) => patch(index, 'action', event.target.value)} aria-label={`${label}: действие кнопки ${index + 1}`}>
              <option value="next">Перейти к блоку</option>
              <option value="callback">Вызвать вход по payload</option>
              <option value="open_mini_app">Открыть Mini App по URL</option>
              <option value="url">Открыть внешнюю ссылку</option>
            </select>
            <button className="icon-btn" type="button" onClick={() => del(index)} title="Удалить кнопку" aria-label={`Удалить кнопку ${index + 1}`}>✕</button>
          </div>

          {button.action === 'next' ? (
            <select className="btnsField__target" value={button.target ?? ''} onChange={(event) => patch(index, 'target', event.target.value)} aria-label={`${label}: следующий блок для кнопки ${index + 1}`}>
              <option value="">— выберите следующий блок —</option>
              {nodeOptions.map((node) => <option key={node.id} value={node.id}>{targetLabel(node)}</option>)}
            </select>
          ) : (
            <input
              className="btnsField__target"
              value={button.target ?? ''}
              onChange={(event) => patch(index, 'target', event.target.value)}
              placeholder={button.action === 'url' || button.action === 'open_mini_app' ? 'https://...' : 'payload входа'}
              aria-label={`${label}: назначение кнопки ${index + 1}`}
            />
          )}
        </div>
      ))}
      <button className="btn btn--ghost" type="button" onClick={add}>+ Добавить кнопку</button>
    </div>
  )
}

// Быстрые ответы блока ask: каждая кнопка — callback, чей target и есть
// сохраняемое значение ответа (process_update._ask_option_answer).
function QuickRepliesField({ value = [], onChange, label }) {
  const items = Array.isArray(value) ? value : []
  const patch = (index, key, nextValue) => {
    onChange(items.map((button, current) => (current === index ? { ...button, [key]: nextValue } : button)))
  }
  const add = () => onChange([...items, { label: '', action: 'callback', target: '' }])
  const del = (index) => onChange(items.filter((_, current) => current !== index))

  return (
    <div className="btnsField">
      {items.map((button, index) => (
        <div className="btnsField__row" key={index}>
          <input
            value={button.label ?? ''}
            onChange={(event) => patch(index, 'label', event.target.value)}
            placeholder="Подпись кнопки"
            aria-label={`${label}: подпись варианта ${index + 1}`}
          />
          <input
            value={button.target ?? ''}
            onChange={(event) => patch(index, 'target', event.target.value)}
            placeholder="Значение ответа"
            aria-label={`${label}: значение варианта ${index + 1}`}
          />
          <button className="icon-btn" type="button" onClick={() => del(index)} title="Удалить вариант" aria-label={`Удалить вариант ${index + 1}`}>✕</button>
        </div>
      ))}
      <button className="btn btn--ghost" type="button" onClick={add}>+ Добавить вариант ответа</button>
      <small className="field__hint">Нажатие сохраняет значение как ответ; свой вариант можно написать текстом.</small>
    </div>
  )
}

// Редактор values-словаря блока save: несколько переменных одним узлом,
// пустое значение стирает переменную (BR-008). Локальные строки нужны, чтобы
// временно совпавшие ключи не схлопывались прямо во время набора.
function KeyValuesField({ value, onChange, label }) {
  // Guard: values в definition — произвольный params-ключ; не-словарь (строка,
  // массив) редактируем как пустой список, а не как посимвольный мусор.
  const [rows, setRows] = useState(() => (
    value && typeof value === 'object' && !Array.isArray(value) ? Object.entries(value) : []
  ))

  // Ключи в словарь уходят подрезанными; строки без ключа не сохраняются.
  const sync = (nextRows) => {
    setRows(nextRows)
    onChange(Object.fromEntries(
      nextRows
        .map(([rowKey, rowValue]) => [rowKey.trim(), rowValue])
        .filter(([rowKey]) => rowKey !== ''),
    ))
  }
  const patch = (index, position, nextValue) => {
    sync(rows.map((row, current) => (
      current === index ? (position === 0 ? [nextValue, row[1]] : [row[0], nextValue]) : row
    )))
  }

  const keyUsage = new Map()
  for (const [rowKey] of rows) {
    const trimmed = rowKey.trim()
    if (trimmed) keyUsage.set(trimmed, (keyUsage.get(trimmed) || 0) + 1)
  }
  const duplicateKeys = [...keyUsage.entries()].filter(([, count]) => count > 1).map(([rowKey]) => rowKey)

  return (
    <div className="btnsField">
      {rows.map(([rowKey, rowValue], index) => (
        <div className="btnsField__row" key={index}>
          <input
            value={rowKey}
            onChange={(event) => patch(index, 0, event.target.value)}
            placeholder="Переменная"
            className={duplicateKeys.includes(rowKey.trim()) ? 'is-invalid' : undefined}
            aria-label={`${label}: переменная ${index + 1}`}
          />
          <input
            value={rowValue}
            onChange={(event) => patch(index, 1, event.target.value)}
            placeholder="Значение (пусто — стереть)"
            aria-label={`${label}: значение ${index + 1}`}
          />
          <button className="icon-btn" type="button" onClick={() => sync(rows.filter((_, current) => current !== index))} title="Удалить строку" aria-label={`Удалить строку ${index + 1}`}>✕</button>
        </div>
      ))}
      <button className="btn btn--ghost" type="button" onClick={() => sync([...rows, ['', '']])}>+ Добавить переменную</button>
      {duplicateKeys.length > 0 && (
        <small className="field__hint field__hint--warn">
          Повторяющиеся переменные: {duplicateKeys.join(', ')} — сохранится только последняя строка.
        </small>
      )}
      <small className="field__hint">Непустой список отключает пару «Ключ/Значение» выше; пустое значение стирает переменную (BR-008).</small>
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
        <button className="btn btn--danger" type="button" onClick={() => onDelete(node.id)}>Удалить триггер</button>
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
      {(def.fields || []).map((field) => {
        if (field.kind === 'buttons') {
          return (
            <div className="field" key={field.key}>
              <span className="field__label">{field.label}</span>
              <ButtonsField
                value={node.data.params[field.key]}
                nodes={nodes}
                ownerId={node.id}
                label={field.label}
                onChange={(value) => onParamsChange(node.id, { [field.key]: value })}
              />
            </div>
          )
        }
        if (field.kind === 'quick_replies') {
          const buttons = Array.isArray(node.data.params[field.key]) ? node.data.params[field.key] : []
          const onlyQuickReplies = buttons.every((button) => button.action === 'callback')
          return (
            <div className="field" key={field.key}>
              <span className="field__label">{field.label}</span>
              {onlyQuickReplies ? (
                <QuickRepliesField
                  value={buttons}
                  label={field.label}
                  onChange={(value) => onParamsChange(node.id, { [field.key]: value })}
                />
              ) : (
                // Кнопки с переходами (например, из скрипт-авторского сценария):
                // показываем полный редактор, чтобы ничего не прятать и не
                // ломать индексы рёбер кнопок.
                <>
                  <ButtonsField
                    value={buttons}
                    nodes={nodes}
                    ownerId={node.id}
                    label={field.label}
                    onChange={(value) => onParamsChange(node.id, { [field.key]: value })}
                  />
                  <small className="field__hint">
                    Пока блок-вопрос ждёт ответ, любая его callback-кнопка работает как быстрый ответ
                    (значение сохраняется как ответ) — «Вызвать вход по payload» здесь не сработает.
                  </small>
                </>
              )}
            </div>
          )
        }
        if (field.kind === 'kv') {
          return (
            <div className="field" key={field.key}>
              <span className="field__label">{field.label}</span>
              <KeyValuesField
                key={`${node.id}:${field.key}`}
                value={node.data.params[field.key]}
                label={field.label}
                onChange={(value) => onParamsChange(node.id, { [field.key]: value })}
              />
            </div>
          )
        }
        return (
          <Field
            key={field.key}
            field={field}
            value={node.data.params[field.key]}
            onChange={(value) => onParamsChange(node.id, { [field.key]: value })}
          />
        )
      })}
      <button className="btn btn--danger" type="button" onClick={() => onDelete(node.id)}>Удалить блок</button>
    </aside>
  )
}
