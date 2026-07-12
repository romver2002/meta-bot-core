const BOT_ID_PATTERN = /^(?:[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})$/i

export class MiniAppConfigError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'MiniAppConfigError'
  }
}

export interface MiniAppConfig {
  botId: string
  apiBaseUrl: string
}

function normalizedApiBaseUrl(value: string): string {
  const trimmed = value.trim()
  if (!trimmed) return ''

  let parsed: URL
  try {
    parsed = new URL(trimmed)
  } catch {
    throw new MiniAppConfigError('Адрес API Mini App настроен неверно.')
  }
  if (parsed.protocol !== 'https:' && !(
    parsed.protocol === 'http:' && (parsed.hostname === '127.0.0.1' || parsed.hostname === 'localhost')
  )) {
    throw new MiniAppConfigError('API Mini App должен быть доступен по HTTPS.')
  }
  return parsed.toString().replace(/\/$/, '')
}

export function readMiniAppConfig(search: string, apiBaseUrl = ''): MiniAppConfig {
  const botId = new URLSearchParams(search).get('bot_id')?.trim() ?? ''
  if (!BOT_ID_PATTERN.test(botId)) {
    throw new MiniAppConfigError('Ссылка запуска Mini App не содержит корректный bot_id.')
  }
  return { botId, apiBaseUrl: normalizedApiBaseUrl(apiBaseUrl) }
}
