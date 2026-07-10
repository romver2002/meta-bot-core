function apiUrl(baseUrl, path) {
  const base = baseUrl.trim().replace(/\/$/, '')
  return `${base}${path}`
}

export class ConstructorApiError extends Error {
  constructor(message, status = null) {
    super(message)
    this.name = 'ConstructorApiError'
    this.status = status
  }
}

async function readBody(response) {
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

function validationMessage(detail) {
  if (!Array.isArray(detail)) return ''
  return detail
    .map((item) => {
      if (typeof item === 'string') return item
      const location = Array.isArray(item?.loc)
        ? item.loc.filter((part) => part !== 'body').join(' → ')
        : ''
      const message = item?.msg === 'Field required' ? 'обязательное поле' : item?.msg
      if (!message) return ''
      return location ? `${location}: ${message}` : message
    })
    .filter(Boolean)
    .join('; ')
}

function responseMessage(response, body) {
  if (response.status >= 500) return 'Ошибка сервера. Изменения не сохранены — повторите попытку позже.'
  if (response.status === 401) return 'Доступ отклонён. Проверьте токен бота или данные авторизации.'
  if (response.status === 403) return 'Доступ запрещён. Проверьте права и секрет вебхука.'

  const detail = typeof body === 'object' && body !== null ? body.detail : body
  const formattedValidation = validationMessage(detail)
  if (formattedValidation) return `Проверьте данные: ${formattedValidation}`
  if (response.status === 404) return 'Запрошенный бот не найден. Возможно, он был удалён в другом сеансе.'
  if (response.status === 409) return 'Данные изменены в другом сеансе. Обновите черновик перед повторной попыткой.'
  if (typeof detail === 'string' && detail.trim()) return detail
  return `${response.status} ${response.statusText}`.trim()
}

async function request(baseUrl, path, options = {}) {
  let response
  try {
    response = await fetch(apiUrl(baseUrl, path), {
      ...options,
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json; charset=utf-8' } : {}),
        ...(options.headers || {}),
      },
    })
  } catch {
    throw new ConstructorApiError('Не удалось связаться с API. Проверьте адрес сервера и локальный запуск.', null)
  }
  const body = await readBody(response)
  if (!response.ok) {
    throw new ConstructorApiError(responseMessage(response, body), response.status)
  }
  return body
}

export function createBot(baseUrl, payload) {
  return request(baseUrl, '/api/bots', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getBot(baseUrl, botId) {
  return request(baseUrl, `/api/bots/${encodeURIComponent(botId)}`)
}

export function saveFlowDraft(baseUrl, botId, payload) {
  return request(baseUrl, `/api/bots/${encodeURIComponent(botId)}/flow`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function publishBot(baseUrl, botId) {
  return request(baseUrl, `/api/bots/${encodeURIComponent(botId)}/publish`, {
    method: 'POST',
  })
}

export function attachMiniApp(baseUrl, botId, payload) {
  return request(baseUrl, `/api/bots/${encodeURIComponent(botId)}/miniapp`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function setConnectionSecret(baseUrl, botId, name, value) {
  return request(baseUrl, `/api/bots/${encodeURIComponent(botId)}/connections/${encodeURIComponent(name)}`, {
    method: 'PUT',
    body: JSON.stringify({ value }),
  })
}

export function setNotificationTarget(baseUrl, botId, role, chatId) {
  return request(baseUrl, `/api/bots/${encodeURIComponent(botId)}/notifications/${encodeURIComponent(role)}`, {
    method: 'PUT',
    body: JSON.stringify({ chat_id: chatId }),
  })
}
