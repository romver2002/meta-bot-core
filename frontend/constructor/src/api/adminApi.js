function apiUrl(baseUrl, path) {
  const base = baseUrl.trim().replace(/\/$/, '')
  return `${base}${path}`
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

async function request(baseUrl, path, options = {}) {
  const response = await fetch(apiUrl(baseUrl, path), {
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json; charset=utf-8' } : {}),
      ...(options.headers || {}),
    },
  })
  const body = await readBody(response)
  if (!response.ok) {
    const detail = typeof body === 'object' && body !== null ? body.detail : body
    throw new Error(detail || `${response.status} ${response.statusText}`)
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
