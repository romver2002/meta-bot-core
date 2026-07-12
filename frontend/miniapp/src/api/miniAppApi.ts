export interface MiniAppAuthResponse {
  external_user_id: string
}

export interface MiniAppResultResponse {
  ok: true
}

export type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>

export class MiniAppApiError extends Error {
  readonly status: number | null

  constructor(message: string, status: number | null = null) {
    super(message)
    this.name = 'MiniAppApiError'
    this.status = status
  }
}

function responseMessage(status: number): string {
  if (status === 401) return 'Не удалось подтвердить запуск. Откройте Mini App заново из чата.'
  if (status === 404) return 'Бот для Mini App не найден.'
  if (status === 422) return 'Запрос Mini App отклонён. Откройте приложение заново из чата.'
  if (status >= 500) return 'Сервис временно недоступен. Повторите попытку позже.'
  return 'Не удалось выполнить запрос Mini App.'
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text) as unknown
  } catch {
    return null
  }
}

function authResponse(value: unknown): MiniAppAuthResponse {
  const externalUserId = typeof value === 'object' && value !== null
    ? (value as Record<string, unknown>).external_user_id
    : undefined
  if (
    typeof externalUserId !== 'string'
  ) {
    throw new MiniAppApiError('Сервис вернул некорректный ответ.')
  }
  return { external_user_id: externalUserId }
}

function resultResponse(value: unknown): MiniAppResultResponse {
  if (typeof value !== 'object' || value === null || (value as Record<string, unknown>).ok !== true) {
    throw new MiniAppApiError('Сервис вернул некорректный ответ.')
  }
  return { ok: true }
}

export class MiniAppApi {
  readonly #baseUrl: string
  readonly #fetch: FetchLike

  constructor(baseUrl: string, fetchImpl: FetchLike = globalThis.fetch.bind(globalThis)) {
    this.#baseUrl = baseUrl.replace(/\/$/, '')
    this.#fetch = fetchImpl
  }

  async authenticate(botId: string, initData: string, signal?: AbortSignal): Promise<MiniAppAuthResponse> {
    const value = await this.#request(botId, 'auth', { init_data: initData }, signal)
    return authResponse(value)
  }

  async submitResult(
    botId: string,
    initData: string,
    result: Record<string, unknown>,
    signal?: AbortSignal,
  ): Promise<MiniAppResultResponse> {
    const value = await this.#request(botId, 'result', { init_data: initData, result }, signal)
    return resultResponse(value)
  }

  async #request(
    botId: string,
    action: 'auth' | 'result',
    payload: Record<string, unknown>,
    signal?: AbortSignal,
  ): Promise<unknown> {
    let response: Response
    try {
      response = await this.#fetch(
        `${this.#baseUrl}/api/bots/${encodeURIComponent(botId)}/miniapp/${action}`,
        {
          method: 'POST',
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json; charset=utf-8',
          },
          body: JSON.stringify(payload),
          credentials: 'omit',
          cache: 'no-store',
          referrerPolicy: 'no-referrer',
          ...(signal ? { signal } : {}),
        },
      )
    } catch {
      throw new MiniAppApiError('Не удалось связаться с сервисом. Проверьте подключение к сети.')
    }

    const body = await readJson(response)
    if (!response.ok) throw new MiniAppApiError(responseMessage(response.status), response.status)
    return body
  }
}
