import { PLATFORMS } from '../domain/catalog.js'

export default function TopBar({
  botName, setBotName, platform, setPlatform,
  validation, showJson, setShowJson, onCheck,
}) {
  const p = PLATFORMS[platform]
  return (
    <header className="topbar" style={{ '--tint': p.tint }}>
      <div className="topbar__left">
        <span className="topbar__avatar">🤖</span>
        <input className="topbar__name" value={botName} onChange={(e) => setBotName(e.target.value)} />

        <span className="badge badge--platform" title="Платформа фиксируется при создании бота и неизменна (BR-002)">
          <span className="badge__dot" /> {p.label} 🔒
        </span>

        <span className="pill">Draft</span>
      </div>

      <div className="topbar__right">
        <div className="seg">
          {Object.values(PLATFORMS).map((pl) => (
            <button key={pl.id}
              className={`seg__btn ${pl.id === platform ? 'seg__btn--on' : ''}`}
              onClick={() => setPlatform(pl.id)}>{pl.label}</button>
          ))}
        </div>

        <button className={`btn btn--ghost ${showJson ? 'btn--ghost-on' : ''}`} onClick={() => setShowJson(!showJson)}>
          {'{ }'} JSON
        </button>
        <button className="btn btn--secondary" onClick={onCheck}>Проверить</button>
        <button className="btn btn--primary" disabled={!validation.ok} title={validation.ok ? 'Опубликовать бота' : 'Есть проблемы — см. «Проверить»'}>
          Опубликовать
          {!validation.ok && <span className="warn">⚠ {validation.problems.length}</span>}
        </button>
      </div>
    </header>
  )
}
