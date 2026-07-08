import { useState } from 'react'

import {
  attachMiniApp,
  createBot,
  getBot,
  publishBot,
  saveFlowDraft,
  setConnectionSecret,
} from '../api/adminApi.js'

function Status({ state }) {
  if (!state.message) return null
  return (
    <div className={`apiStatus apiStatus--${state.kind}`}>
      {state.message}
    </div>
  )
}

function Field({ label, children }) {
  return (
    <label className="apiField">
      <span>{label}</span>
      {children}
    </label>
  )
}

function Section({ title, children, open = false }) {
  return (
    <details className="apiSection" open={open}>
      <summary>{title}</summary>
      <div className="apiSection__body">{children}</div>
    </details>
  )
}

export default function ApiPanel({ flow, validation, botName, platform }) {
  const [baseUrl, setBaseUrl] = useState('')
  const [botId, setBotId] = useState('')
  const [botToken, setBotToken] = useState('')
  const [rowVersion, setRowVersion] = useState(null)
  const [flowId, setFlowId] = useState('')
  const [miniAppUrl, setMiniAppUrl] = useState('')
  const [miniAppTitle, setMiniAppTitle] = useState('')
  const [secretName, setSecretName] = useState('openrouter_api_key')
  const [secretValue, setSecretValue] = useState('')
  const [busy, setBusy] = useState(null)
  const [status, setStatus] = useState({ kind: 'idle', message: '' })

  const run = async (name, action) => {
    setBusy(name)
    setStatus({ kind: 'idle', message: '' })
    try {
      const result = await action()
      setStatus({ kind: 'ok', message: result })
    } catch (error) {
      setStatus({ kind: 'bad', message: error.message })
    } finally {
      setBusy(null)
    }
  }

  const create = () => run('create', async () => {
    if (!botToken.trim()) throw new Error('Нужен токен уже созданного бота')
    const bot = await createBot(baseUrl, {
      name: botName,
      platform,
      token: botToken,
    })
    setBotId(bot.id)
    setBotToken('')
    setRowVersion(null)
    return `Бот создан: ${bot.id}`
  })

  const load = () => run('load', async () => {
    if (!botId.trim()) throw new Error('Укажите bot_id')
    const bot = await getBot(baseUrl, botId.trim())
    setFlowId(bot.flow_id || '')
    return `Статус бота: ${bot.status}`
  })

  const save = () => run('save', async () => {
    if (!botId.trim()) throw new Error('Укажите bot_id')
    if (!validation.ok) throw new Error(`Сначала исправьте: ${validation.problems.join('; ')}`)
    const saved = await saveFlowDraft(baseUrl, botId.trim(), {
      definition: flow.definition,
      row_version: rowVersion,
      name: botName,
    })
    setFlowId(saved.flow_id)
    setRowVersion(saved.row_version)
    return `Черновик сохранён, row_version=${saved.row_version}`
  })

  const publish = () => run('publish', async () => {
    if (!botId.trim()) throw new Error('Укажите bot_id')
    if (!validation.ok) throw new Error(`Сначала исправьте: ${validation.problems.join('; ')}`)
    const result = await publishBot(baseUrl, botId.trim())
    return `Опубликовано: ${result.bot.status}`
  })

  const attach = () => run('miniapp', async () => {
    if (!botId.trim()) throw new Error('Укажите bot_id')
    if (!miniAppUrl.trim().startsWith('https://')) throw new Error('Mini app URL должен начинаться с https://')
    await attachMiniApp(baseUrl, botId.trim(), {
      url: miniAppUrl.trim(),
      title: miniAppTitle.trim(),
    })
    return 'Mini app привязана к боту'
  })

  const saveSecret = () => run('secret', async () => {
    if (!botId.trim()) throw new Error('Укажите bot_id')
    if (!secretName.trim()) throw new Error('Укажите имя секрета')
    if (!secretValue) throw new Error('Укажите значение секрета')
    await setConnectionSecret(baseUrl, botId.trim(), secretName.trim(), secretValue)
    setSecretValue('')
    return `Секрет подключения сохранён: ${secretName.trim()}`
  })

  const disabledByValidation = !validation.ok

  return (
    <aside className="apiPanel">
      <div className="apiPanel__head">
        <div>
          <div className="apiPanel__title">Боты и публикация</div>
          <div className="apiPanel__meta">
            {flowId ? `flow ${flowId}` : 'draft not saved'} · row {rowVersion ?? 'new'}
          </div>
        </div>
        <button className="btn btn--ghost" onClick={load} disabled={busy === 'load' || !botId.trim()}>
          Обновить
        </button>
      </div>

      <div className="apiGrid">
        <Field label="bot_id">
          <input value={botId} onChange={(event) => setBotId(event.target.value)} placeholder="после create или из API" />
        </Field>
        <Field label="row_version">
          <input value={rowVersion ?? ''} onChange={(event) => setRowVersion(event.target.value ? Number(event.target.value) : null)} placeholder="new" />
        </Field>
      </div>

      <div className="apiActions">
        <button className="btn btn--secondary" onClick={save} disabled={busy === 'save' || disabledByValidation || !botId.trim()}>
          Сохранить draft
        </button>
        <button className="btn btn--primary" onClick={publish} disabled={busy === 'publish' || disabledByValidation || !botId.trim()}>
          Опубликовать
        </button>
      </div>

      <Section title="Создать бота">
        <Field label="токен бота">
          <input type="password" value={botToken} onChange={(event) => setBotToken(event.target.value)} placeholder="не сохраняется во фронте" />
        </Field>
        <button className="btn btn--secondary" onClick={create} disabled={busy === 'create' || !botToken.trim()}>
          Создать бота
        </button>
      </Section>

      <Section title="Mini app">
        <Field label="HTTPS URL">
          <input value={miniAppUrl} onChange={(event) => setMiniAppUrl(event.target.value)} placeholder="https://app.example.com" />
        </Field>
        <Field label="title">
          <input value={miniAppTitle} onChange={(event) => setMiniAppTitle(event.target.value)} placeholder="Витрина" />
        </Field>
        <button className="btn btn--secondary" onClick={attach} disabled={busy === 'miniapp' || !botId.trim() || !miniAppUrl.trim()}>
          Привязать mini app
        </button>
      </Section>

      <Section title="Секреты подключений">
        <Field label="name">
          <input value={secretName} onChange={(event) => setSecretName(event.target.value)} placeholder="openrouter_api_key" />
        </Field>
        <Field label="value">
          <input type="password" value={secretValue} onChange={(event) => setSecretValue(event.target.value)} placeholder="значение не попадает в Flow" />
        </Field>
        <button className="btn btn--secondary" onClick={saveSecret} disabled={busy === 'secret' || !botId.trim() || !secretValue}>
          Сохранить секрет
        </button>
      </Section>

      <Section title="Подключение к API">
        <Field label="API base">
          <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="/ через Vite proxy" />
        </Field>
      </Section>

      <Status state={status} />
    </aside>
  )
}
