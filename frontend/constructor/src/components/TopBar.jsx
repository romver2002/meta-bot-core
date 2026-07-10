import { PLATFORMS } from '../domain/catalog.js'

export default function TopBar({
  botName,
  setBotName,
  platform,
  setPlatform,
  platformLocked,
  status,
  showJson,
  setShowJson,
  onCheck,
  onOpenPublish,
  paletteOpen,
  onTogglePalette,
  rightOpen,
  onToggleRight,
}) {
  const activePlatform = PLATFORMS[platform]
  const nameLabel = platformLocked ? 'Название сценария' : 'Название бота'
  return (
    <header className="topbar" style={{ '--tint': activePlatform.tint }}>
      <div className="topbar__left">
        <span className="topbar__avatar" aria-hidden="true">MB</span>
        <div className="topbar__titleGroup">
          <span className="topbar__product">Конструктор сценария</span>
          <input
            className="topbar__name"
            value={botName}
            onChange={(event) => setBotName(event.target.value)}
            aria-label={nameLabel}
            placeholder={nameLabel}
            title={platformLocked ? 'После подключения это название сценария; имя бота меняется в настройках платформы.' : undefined}
          />
        </div>

        <span className={`pill pill--${status.kind}`} title={status.detail || status.text}>
          {status.text}
        </span>
      </div>

      <div className="topbar__right">
        <div className="platformControl">
          <span className="platformControl__label">Платформа</span>
          <div className="seg" aria-label="Платформа бота">
            {Object.values(PLATFORMS).map((item) => (
              <button
                key={item.id}
                type="button"
                className={`seg__btn ${item.id === platform ? 'seg__btn--on' : ''}`}
                onClick={() => setPlatform(item.id)}
                disabled={platformLocked}
                title={platformLocked ? 'Платформа закреплена после подключения бота' : `Собрать сценарий для ${item.label}`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <button
          type="button"
          className={`btn btn--ghost btn--toggle ${paletteOpen ? 'btn--ghost-on' : ''}`}
          onClick={onTogglePalette}
          aria-pressed={paletteOpen}
        >
          Блоки
        </button>
        <button
          type="button"
          className={`btn btn--ghost btn--toggle ${rightOpen ? 'btn--ghost-on' : ''}`}
          onClick={onToggleRight}
          aria-pressed={rightOpen}
        >
          Панель
        </button>
        <button type="button" className={`btn btn--ghost ${showJson ? 'btn--ghost-on' : ''}`} onClick={() => setShowJson(!showJson)}>
          Данные Flow
        </button>
        <button type="button" className="btn btn--secondary" onClick={onCheck}>Проверить</button>
        <button type="button" className="btn btn--primary" onClick={onOpenPublish}>Открыть публикацию</button>
      </div>
    </header>
  )
}
