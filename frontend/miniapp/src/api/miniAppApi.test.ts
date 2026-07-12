import { describe, expect, it, vi } from 'vitest'

import { MiniAppApi, MiniAppApiError } from './miniAppApi'
import type { FetchLike } from './miniAppApi'

const BOT_ID = '0123456789abcdef0123456789abcdef'
const INIT_DATA = 'query_id=sensitive&hash=never-log-this'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('MiniAppApi', () => {
  it('sends raw init data to auth with cookies omitted', async () => {
    const fetchMock = vi.fn<FetchLike>(async () => jsonResponse({ external_user_id: '777' }))
    const api = new MiniAppApi('https://api.example.test/', fetchMock)

    await expect(api.authenticate(BOT_ID, INIT_DATA)).resolves.toEqual({ external_user_id: '777' })

    const [url, options] = fetchMock.mock.calls[0] ?? []
    expect(url).toBe(`https://api.example.test/api/bots/${BOT_ID}/miniapp/auth`)
    expect(options?.method).toBe('POST')
    expect(options?.credentials).toBe('omit')
    expect(options?.referrerPolicy).toBe('no-referrer')
    expect(JSON.parse(String(options?.body))).toEqual({ init_data: INIT_DATA })
  })

  it('submits the explicit result contract', async () => {
    const fetchMock = vi.fn<FetchLike>(async () => jsonResponse({ ok: true }))
    const api = new MiniAppApi('', fetchMock)

    await expect(api.submitResult(BOT_ID, INIT_DATA, { action: 'confirmed' })).resolves.toEqual({ ok: true })

    const [url, options] = fetchMock.mock.calls[0] ?? []
    expect(url).toBe(`/api/bots/${BOT_ID}/miniapp/result`)
    expect(JSON.parse(String(options?.body))).toEqual({
      init_data: INIT_DATA,
      result: { action: 'confirmed' },
    })
  })

  it('does not expose backend details or init data in errors', async () => {
    const fetchMock = vi.fn<FetchLike>(async () => jsonResponse({ detail: INIT_DATA }, 401))
    const api = new MiniAppApi('', fetchMock)

    const error = await api.authenticate(BOT_ID, INIT_DATA).catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(MiniAppApiError)
    expect((error as Error).message).not.toContain(INIT_DATA)
    expect((error as MiniAppApiError).status).toBe(401)
  })

  it('normalizes a network failure', async () => {
    const fetchMock = vi.fn<FetchLike>(async () => { throw new TypeError('request leaked secret') })
    const api = new MiniAppApi('', fetchMock)

    await expect(api.authenticate(BOT_ID, INIT_DATA)).rejects.toThrow('Не удалось связаться с сервисом')
  })
})
