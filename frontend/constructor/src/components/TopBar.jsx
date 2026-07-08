import { PLATFORMS } from '../domain/catalog.js'

export default function TopBar({
  botName, setBotName, platform, setPlatform,
  validation, showJson, setShowJson, onCheck,
  paletteOpen, setPaletteOpen, rightOpen, setRightOpen,
}) {
  const p = PLATFORMS[platform]
  return (
    <header className="topbar" style={{ '--tint': p.tint }}>
      <div className="topbar__left">
        <span className="topbar__avatar">MB</span>
        <input className="topbar__name" value={botName} onChange={(e) => setBotName(e.target.value)} />

        <span className="badge badge--platform" title="Платформа фиксируется при создании бота и неизменна (BR-002)">
          <span className="badge__dot" /> {p.label}
        </span>

        <span className={`pill ${validation.ok ? 'pill--ok' : 'pill--bad'}`}>
          {validation.ok ? 'publish-ready' : `${validation.problems.length} issues`}
        </span>
      </div>

      <div className="topbar__right">
        <button
          className={`btn btn--ghost btn--toggle ${paletteOpen ? 'btn--ghost-on' : ''}`}
          onClick={() => setPaletteOpen(!paletteOpen)}
          title="Открыть или закрыть палитру блоков"
        >
          Блоки
        </button>
        <button
          className={`btn btn--ghost btn--toggle ${rightOpen ? 'btn--ghost-on' : ''}`}
          onClick={() => setRightOpen(!rightOpen)}
          title="Открыть или закрыть правую панель"
        >
          Панель
        </button>

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
      </div>
    </header>
  )
}
