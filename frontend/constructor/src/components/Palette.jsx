import { TRIGGERS, BLOCKS, SOON_BLOCKS, blockAvailable } from '../domain/catalog.js'

function Item({ item, group, disabled, reason }) {
  const onDragStart = (e) => {
    if (disabled) { e.preventDefault(); return }
    e.dataTransfer.setData('application/mbc', JSON.stringify({ type: item.type, label: item.label, icon: item.icon, group }))
    e.dataTransfer.effectAllowed = 'move'
  }
  return (
    <div
      className={`pal ${disabled ? 'pal--off' : ''}`}
      draggable={!disabled}
      onDragStart={onDragStart}
      title={disabled ? reason : item.hint}
      style={{ '--accent': item.color || '#059669' }}
    >
      <span className="pal__icon">{item.icon}</span>
      <span className="pal__label">{item.label}</span>
      {item.sandbox && <span className="pal__lock">🔒</span>}
    </div>
  )
}

export default function Palette({ platform }) {
  return (
    <aside className="palette">
      <div className="palette__hint">Перетащите блок на холст →</div>

      <div className="palette__group">Триггеры · входы</div>
      {TRIGGERS.map((t) => <Item key={t.type} item={t} group="trigger" />)}

      <div className="palette__group">Блоки</div>
      {BLOCKS.map((b) => {
        const ok = blockAvailable(b, platform)
        return (
          <Item key={b.type} item={b} group="block" disabled={!ok}
            reason="Недоступно на этой платформе (CapabilityMatrix, BR-006)" />
        )
      })}

      <div className="palette__group">Скоро · вне MVP</div>
      {SOON_BLOCKS.map((b) => (
        <Item key={b.type} item={b} group="block" disabled reason={b.hint} />
      ))}
    </aside>
  )
}
