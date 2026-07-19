import { useRef, useState } from 'react'

import {
  attachMiniApp,
  createBot,
  getBot,
  getFlowDraft,
  listBots,
  publishBot,
  saveFlowDraft,
  setConnectionSecret,
  setNotificationTarget,
} from '../api/adminApi.js'

function Status({ state, onDismiss }) {
  if (!state.message) return null
  const isError = state.kind === 'bad'
  return (
    <div className={`apiStatus apiStatus--${state.kind}`} role={isError ? 'alert' : 'status'} aria-live={isError ? 'assertive' : 'polite'}>
      <span className="apiStatus__message">{state.message}</span>
      <button className="icon-btn apiStatus__dismiss" type="button" onClick={onDismiss} aria-label="Закрыть сообщение">✕</button>
    </div>
  )
}

function Field({ label, children, hint }) {
  return (
    <label className="apiField">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  )
}

function Section({ title, children, open = false, note }) {
  return (
    <details className="apiSection" open={open}>
      <summary>{title}</summary>
      <div className="apiSection__body">
        {note && <p className="apiSection__note">{note}</p>}
        {children}
      </div>
    </details>
  )
}

function messages(validation) {
  return validation.problems.map((problem) => problem.message).join('; ')
}

function platformName(platform) {
  return platform === 'max' ? 'MAX' : 'Telegram'
}

function allowedApiOrigin(baseUrl) {
  const value = baseUrl.trim()
  if (!value || value.startsWith('/')) return true
  try {
    const url = new URL(value, window.location.origin)
    return url.origin === window.location.origin || ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
  } catch {
    return false
  }
}

function ValidationSummary({ validation, onCheck }) {
  if (validation.ok) return null
  return (
    <div className="apiPanel__validation" role="alert">
      <strong>Нужно исправить: {validation.problems.length}</strong>
      <ul>
        {validation.problems.map((problem, index) => <li key={`${problem.message}-${index}`}>{problem.message}</li>)}
      </ul>
      <button className="apiPanel__problem" type="button" onClick={onCheck}>Показать на схеме</button>
    </div>
  )
}

function readableError(error) {
  const message = error instanceof Error ? error.message : 'Неизвестная ошибка. Повторите попытку.'
  return error?.status === 409 || /row_version|черновик.*измен/i.test(message)
    ? 'Черновик изменён в другом сеансе. Сохранение остановлено, чтобы не потерять данные.'
    : message
}

export default function ApiPanel({
  flow,
  validation,
  publishValidation,
  botName,
  platform,
  session,
  onSessionChange,
  onConnected,
  onOpened,
  onSaved,
  onPublished,
  isDirty,
  canvasTouched,
  onCheck,
}) {
  const [botToken, setBotToken] = useState('')
  const [openBotId, setOpenBotId] = useState('')
  const [botList, setBotList] = useState(null)
  const [secretName, setSecretName] = useState('integration_api_key')
  const [secretValue, setSecretValue] = useState('')
  const activeOperationRef = useRef(false)
  const patchSession = (patch) => onSessionChange((current) => ({ ...current, ...patch }))
  const isConnected = Boolean(session.botId)
  const isBusy = Boolean(session.busy)
  const usesHttp = flow.definition.nodes.some((node) => node.type === 'http_request')
  const usesNotify = flow.definition.nodes.some((node) => node.type === 'notify')

  const run = async (name, action) => {
    if (activeOperationRef.current) return
    activeOperationRef.current = true
    patchSession({ busy: name, apiStatus: { kind: 'idle', message: '' } })
    try {
      const message = await action()
      patchSession({ apiStatus: { kind: 'ok', message } })
    } catch (error) {
      patchSession({ apiStatus: { kind: 'bad', message: readableError(error) } })
    } finally {
      activeOperationRef.current = false
      patchSession({ busy: null })
    }
  }

  const connect = () => run('connect', async () => {
    if (!botToken.trim()) throw new Error('Введите токен уже зарегистрированного бота')
    if (!allowedApiOrigin(session.baseUrl)) {
      throw new Error('В целях безопасности токен можно отправить только на текущий сайт или локальный API.')
    }
    const bot = await createBot(session.baseUrl, {
      name: botName.trim() || 'Новый бот',
      platform,
      token: botToken,
    })
    setBotToken('')
    // Идемпотентный connect (BR-009): тот же токен возвращает существующего
    // бота — если у него уже есть сценарий, ведём пользователя прямо в него.
    if (bot.flow_id) {
      let draft = null
      try {
        draft = await getFlowDraft(session.baseUrl, bot.id)
      } catch {
        // Бот уже подключён на сервере — сбой чтения черновика не должен
        // выглядеть как провал подключения.
        onConnected(bot)
        return 'Бот подключён, но сценарий с сервера загрузить не удалось — нажмите «Перечитать сценарий с сервера».'
      }
      if (draft) {
        const replaceCanvas = !canvasTouched
          || window.confirm('У этого бота уже есть сценарий на сервере. Открыть его? Текущая канва будет заменена.')
        if (replaceCanvas) {
          onOpened(bot, draft)
          return `Бот подключён — сценарий «${(draft.name || bot.name).trim() || bot.id}» загружен с сервера`
        }
        // Канва остаётся локальной, но row_version серверного черновика нужен:
        // иначе «Сохранить» упрётся в ложный 409 «изменён в другом сеансе».
        onConnected(bot, draft)
        return 'Бот подключён; серверный сценарий не открыт — «Сохранить» перезапишет его текущей канвой, «Перечитать сценарий с сервера» вернёт серверную версию.'
      }
    }
    onConnected(bot)
    return `Бот подключён к конструктору. Теперь сохраните сценарий.`
  })

  // Загрузка сценария с сервера: карточка бота + черновик (204 -> чистый лист).
  const loadFromServer = async (botId) => {
    const bot = await getBot(session.baseUrl, botId)
    const draft = await getFlowDraft(session.baseUrl, botId)
    onOpened(bot, draft)
    return draft
      ? `Сценарий «${(draft.name || bot.name).trim() || bot.id}» загружен с сервера`
      : 'У бота ещё нет черновика — соберите сценарий и сохраните его'
  }

  const confirmReplaceCanvas = () => (
    !canvasTouched
    || window.confirm('Заменить текущий сценарий данными с сервера? Несохранённые изменения будут потеряны.')
  )

  const openExisting = () => run('open', async () => {
    const botId = openBotId.trim()
    if (!botId) throw new Error('Укажите ID бота, полученный при подключении')
    if (!confirmReplaceCanvas()) return 'Загрузка отменена — текущий сценарий не тронут'
    const message = await loadFromServer(botId)
    setOpenBotId('')
    return message
  })

  const reloadFromServer = () => run('open', async () => {
    if (!isConnected) throw new Error('Сначала подключите бота')
    if (!confirmReplaceCanvas()) return 'Загрузка отменена — текущий сценарий не тронут'
    return loadFromServer(session.botId)
  })

  const refreshBotList = () => run('bots', async () => {
    const registry = await listBots(session.baseUrl)
    setBotList(registry.bots)
    return registry.bots.length > 0
      ? `В реестре ${registry.bots.length} бот(ов)`
      : 'Ботов пока нет — подключите первого по токену'
  })

  const openFromList = (botId) => run('open', async () => {
    if (!confirmReplaceCanvas()) return 'Загрузка отменена — текущий сценарий не тронут'
    return loadFromServer(botId)
  })

  const save = () => run('save', async () => {
    if (!isConnected) throw new Error('Сначала подключите уже зарегистрированного бота')
    if (!validation.ok) throw new Error(`Исправьте сценарий: ${messages(validation)}`)
    const saved = await saveFlowDraft(session.baseUrl, session.botId, {
      definition: flow.definition,
      row_version: session.rowVersion,
      name: botName.trim(),
    })
    onSaved(saved)
    return 'Черновик сценария сохранён'
  })

  const publish = () => run('publish', async () => {
    if (!isConnected) throw new Error('Сначала подключите уже зарегистрированного бота')
    if (!publishValidation.ok) throw new Error(`Пока нельзя публиковать: ${messages(publishValidation)}`)
    if (session.rowVersion === null || isDirty) throw new Error('Сначала сохраните текущую версию сценария')
    const result = await publishBot(session.baseUrl, session.botId)
    onPublished(result.bot)
    return 'Сценарий опубликован и бот активирован'
  })

  const attach = () => run('miniapp', async () => {
    if (!isConnected) throw new Error('Сначала подключите бота')
    if (!session.miniAppUrl.trim().startsWith('https://')) throw new Error('Адрес Mini App должен начинаться с https://')
    await attachMiniApp(session.baseUrl, session.botId, {
      url: session.miniAppUrl.trim(),
      title: session.miniAppTitle.trim(),
    })
    patchSession({ miniAppAttached: true })
    return 'Mini App привязана к боту'
  })

  const saveSecret = () => run('secret', async () => {
    if (!isConnected) throw new Error('Сначала подключите бота')
    if (!secretName.trim()) throw new Error('Укажите имя секрета')
    if (!secretValue) throw new Error('Введите значение секрета')
    await setConnectionSecret(session.baseUrl, session.botId, secretName.trim(), secretValue)
    setSecretValue('')
    return `Секрет «${secretName.trim()}» сохранён вне сценария`
  })

  const saveNotificationTarget = () => run('notify', async () => {
    if (!isConnected) throw new Error('Сначала подключите бота')
    if (!session.notificationRole.trim()) throw new Error('Укажите роль адресата')
    if (!session.notificationChatId.trim()) throw new Error('Укажите chat ID адресата')
    await setNotificationTarget(
      session.baseUrl,
      session.botId,
      session.notificationRole.trim(),
      session.notificationChatId.trim(),
    )
    return `Адресат роли «${session.notificationRole.trim()}» сохранён`
  })

  const publishDisabled = (
    isBusy
    || !isConnected
    || !publishValidation.ok
    || session.rowVersion === null
    || isDirty
  )

  return (
    <aside className="apiPanel">
      <div className="apiPanel__head">
        <div>
          <div className="apiPanel__title">Публикация сценария</div>
          <div className="apiPanel__meta">
            {isConnected ? `Бот подключён · ${session.status === 'published' ? 'опубликован' : 'черновик'}` : 'Подключите бота, затем сохраните и опубликуйте сценарий'}
          </div>
        </div>
      </div>
      <Status state={session.apiStatus} onDismiss={() => patchSession({ apiStatus: { kind: 'idle', message: '' } })} />

      <Section
        title={isConnected ? '1. Бот подключён' : '1. Подключите зарегистрированного бота'}
        open={!isConnected}
        note="Конструктор не создаёт аккаунт бота в Telegram или MAX. Он подключает уже выданный токен к сценарию."
      >
        {isConnected ? (
          <>
            <div className="connectionCard">
              <strong>Подключённый бот</strong>
              <span>{session.connectedBotName || 'Имя доступно в настройках платформы'} · {platformName(platform)} · платформа закреплена</span>
              <small title="По этому ID сценарий можно снова открыть в другом сеансе">ID: <code>{session.botId}</code></small>
            </div>
            <button className="btn btn--secondary" type="button" onClick={reloadFromServer} disabled={isBusy}>
              Перечитать сценарий с сервера
            </button>
          </>
        ) : (
          <>
            <Field label="Токен уже зарегистрированного бота" hint="Токен используется только для подключения и не попадает в Flow.">
              <input type="password" value={botToken} onChange={(event) => setBotToken(event.target.value)} placeholder="Вставьте токен бота" autoComplete="off" />
            </Field>
            <button className="btn btn--secondary" type="button" onClick={connect} disabled={isBusy || !botToken.trim()}>
              Подключить {platformName(platform)}-бота
            </button>
            <Field label="…или откройте уже подключённого бота" hint="ID показан в карточке бота после подключения. Сценарий загрузится с сервера, узлы будут расставлены автоматически.">
              <input value={openBotId} onChange={(event) => setOpenBotId(event.target.value)} placeholder="ID бота (UUID)" autoComplete="off" />
            </Field>
            <button className="btn btn--secondary" type="button" onClick={openExisting} disabled={isBusy || !openBotId.trim()}>
              Открыть сценарий с сервера
            </button>
          </>
        )}
      </Section>

      <Section title="Мои боты" note="Реестр ботов этого сервера: статус, платформа и открытие сценария в один клик.">
        <button className="btn btn--secondary" type="button" onClick={refreshBotList} disabled={isBusy}>
          {botList === null ? 'Показать моих ботов' : 'Обновить список'}
        </button>
        {Array.isArray(botList) && botList.length === 0 && (
          <p className="apiSection__note">Ботов пока нет — подключите первого по токену в шаге 1.</p>
        )}
        {Array.isArray(botList) && botList.length > 0 && (
          <ul className="botList">
            {botList.map((bot) => (
              <li key={bot.id} className={`botList__item ${bot.id === session.botId ? 'botList__item--current' : ''}`}>
                <div className="botList__info">
                  <strong>{bot.name || 'Без имени'}</strong>
                  <small>
                    {platformName(bot.platform)} · {bot.status === 'published' ? 'опубликован' : 'черновик'}
                    {bot.id === session.botId ? ' · открыт сейчас' : ''}
                  </small>
                </div>
                <button className="btn btn--secondary" type="button" onClick={() => openFromList(bot.id)} disabled={isBusy}>
                  Открыть
                </button>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="2. Сохраните черновик" open={isConnected} note="Сохраняется только описание Flow. Перемещения узлов не меняют опубликованную логику.">
        <div className="apiActions apiActions--single">
          <button className="btn btn--secondary" type="button" onClick={save} disabled={isBusy || !isConnected || !validation.ok || (!isDirty && session.rowVersion !== null)}>
            {session.rowVersion === null ? 'Сохранить сценарий' : isDirty ? 'Сохранить изменения' : 'Черновик сохранён'}
          </button>
        </div>
        <ValidationSummary validation={validation} onCheck={onCheck} />
      </Section>

      <Section
        title="3. Публикация"
        open={isConnected && publishValidation.ok}
        note="Перед публикацией проверяются структура Flow, возможности платформы и обязательные зависимости."
      >
        <div className="apiActions apiActions--single">
          <button className="btn btn--primary" type="button" onClick={publish} disabled={publishDisabled}>
            {session.status === 'published' ? 'Опубликовать новую версию' : 'Опубликовать сценарий'}
          </button>
        </div>
        {isDirty && session.rowVersion !== null && <p className="apiPanel__warning">Есть несохранённые изменения — сначала сохраните черновик.</p>}
        {isConnected && <ValidationSummary validation={publishValidation} onCheck={onCheck} />}
      </Section>

      <Section title="Mini App" note="Нужно только если в сценарии есть блок «Открыть mini app». URL проверяется на HTTPS.">
        <Field label="HTTPS-адрес">
          <input value={session.miniAppUrl} onChange={(event) => patchSession({ miniAppUrl: event.target.value, miniAppAttached: false })} placeholder="https://app.example.com" />
        </Field>
        <Field label="Название (необязательно)">
          <input value={session.miniAppTitle} onChange={(event) => patchSession({ miniAppTitle: event.target.value })} placeholder="Витрина" />
        </Field>
        <button className="btn btn--secondary" type="button" onClick={attach} disabled={isBusy || !isConnected || !session.miniAppUrl.trim()}>
          {session.miniAppAttached ? 'Mini App привязана' : 'Привязать Mini App'}
        </button>
      </Section>

      {usesNotify && (
        <Section title="Адресат уведомлений" note="Роль остаётся в Flow, а chat ID хранится отдельно от сценария.">
          <Field label="Роль из блока «Уведомить команду»">
            <input value={session.notificationRole} onChange={(event) => patchSession({ notificationRole: event.target.value })} placeholder="sales" />
          </Field>
          <Field label="Chat ID адресата">
            <input value={session.notificationChatId} onChange={(event) => patchSession({ notificationChatId: event.target.value })} placeholder="Например, 123456789" />
          </Field>
          <button className="btn btn--secondary" type="button" onClick={saveNotificationTarget} disabled={isBusy || !isConnected}>
            Сохранить адресата
          </button>
        </Section>
      )}

      {usesHttp && (
        <Section title="Секреты интеграций" note="Укажите имя в блоке как {{secret:имя}}. Значение не попадёт в Flow, JSON или журнал конструктора.">
          <Field label="Имя секрета">
            <input value={secretName} onChange={(event) => setSecretName(event.target.value)} placeholder="crm_api_key" autoComplete="off" />
          </Field>
          <Field label="Значение">
            <input type="password" value={secretValue} onChange={(event) => setSecretValue(event.target.value)} placeholder="Введите значение" autoComplete="off" />
          </Field>
          <button className="btn btn--secondary" type="button" onClick={saveSecret} disabled={isBusy || !isConnected || !secretValue}>
            Сохранить секрет
          </button>
        </Section>
      )}

      <Section title="Для разработки">
        <Field label="Базовый URL API" hint="Пустое значение использует Vite proxy. Токен можно отправить только на текущий сайт или localhost.">
          <input value={session.baseUrl} onChange={(event) => patchSession({ baseUrl: event.target.value })} placeholder="/" />
        </Field>
      </Section>
    </aside>
  )
}
