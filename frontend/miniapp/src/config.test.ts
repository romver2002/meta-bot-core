import { describe, expect, it } from 'vitest'

import { MiniAppConfigError, readMiniAppConfig } from './config'

describe('readMiniAppConfig', () => {
  it('reads bot_id and normalizes the API origin', () => {
    expect(readMiniAppConfig(
      '?bot_id=0123456789abcdef0123456789abcdef',
      'https://api.example.test/',
    )).toEqual({
      botId: '0123456789abcdef0123456789abcdef',
      apiBaseUrl: 'https://api.example.test',
    })
  })

  it('rejects a missing or malformed bot_id', () => {
    expect(() => readMiniAppConfig('?bot_id=bot-1')).toThrow(MiniAppConfigError)
    expect(() => readMiniAppConfig('')).toThrow('bot_id')
  })

  it('allows HTTP only for local development', () => {
    expect(readMiniAppConfig('?bot_id=0123456789abcdef0123456789abcdef', 'http://127.0.0.1:8000'))
      .toMatchObject({ apiBaseUrl: 'http://127.0.0.1:8000' })
    expect(() => readMiniAppConfig(
      '?bot_id=0123456789abcdef0123456789abcdef',
      'http://api.example.test',
    )).toThrow('HTTPS')
  })
})
