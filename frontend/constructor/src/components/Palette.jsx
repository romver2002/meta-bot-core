import { TRIGGERS, BLOCKS, SOON_BLOCKS, blockAvailable } from '../domain/catalog.js'

function Item({ item, group, disabled, reason, onAdd }) {
  const onDragStart = (e) => {
    if (disabled) { e.preventDefault(); return }
    e.dataTransfer.setData('application/mbc', JSON.stringify({ type: item.type, label: item.label, icon: item.icon, group }))
    e.dataTransfer.effectAllowed = 'move'
  }
  return (
    <button
      type="button"
      className={`pal ${disabled ? 'pal--off' : ''}`}
      draggable={!disabled}
      onDragStart={onDragStart}
      onClick={() => onAdd(item, group)}
      disabled={disabled}
      title={disabled ? reason : item.hint}
      style={{ '--accent': item.color || '#059669' }}
    >
      <span className="pal__icon">{item.icon}</span>
      <span className="pal__label">{item.label}</span>
      {item.sandbox && <span className="pal__lock">🔒</span>}
    </button>
  )
}

function Group({ title, children }) {
  return (
    <section>
      <div className="palette__group">{title}</div>
      {children}
    </section>
  )
}

export default function Palette({ platform, onAdd }) {
  const renderItems = (items, group) => items.map((item) => {
    const available = group === 'block' ? blockAvailable(item, platform) : true
    return (
      <Item
        key={item.type}
        item={item}
        group={group}
        disabled={!available}
        reason="Недоступно на этой платформе (CapabilityMatrix, BR-006)"
        onAdd={onAdd}
      />
    )
  })
  const blocksByCategory = BLOCKS.reduce((groups, block) => {
    const category = block.category || 'Блоки'
    groups[category] = [...(groups[category] || []), block]
    return groups
  }, {})

  return (
    <aside className="palette">
      <div className="palette__hint">Перетащите блок на холст или нажмите, чтобы добавить его в центр схемы.</div>

      <Group title="Как пользователь входит">
        {renderItems(TRIGGERS, 'trigger')}
      </Group>

      {Object.entries(blocksByCategory).map(([category, items]) => (
        <Group key={category} title={category}>{renderItems(items, 'block')}</Group>
      ))}

      <Group title="Скоро · вне MVP">
        {SOON_BLOCKS.map((item) => (
          <Item key={item.type} item={item} group="block" disabled reason={item.hint} onAdd={onAdd} />
        ))}
      </Group>
    </aside>
  )
}
