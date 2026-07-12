import { describe, expect, it, vi } from 'vitest'

import type { BridgeHost, MaxWebAppBridge, TelegramWebAppBridge } from './bridgeTypes'
import { createMiniAppPlatform } from './factory'
import {
  detectLaunchPlatform,
  loadPlatformBridge,
  MAX_BRIDGE_SOURCE,
  TELEGRAM_BRIDGE_SOURCE,
} from './loadBridge'

describe('platform bridge', () => {
  it('detects launch markers without needing a preloaded bridge', () => {
    expect(detectLaunchPlatform({}, '#tgWebAppData=sensitive&tgWebAppVersion=9')).toBe('telegram')
    expect(detectLaunchPlatform({}, '#WebAppData=sensitive&WebAppVersion=1')).toBe('max')
    expect(detectLaunchPlatform({}, '')).toBe('browser')
  })

  it('loads only the expected official bridge script', async () => {
    const telegram: TelegramWebAppBridge = { initData: 'signed' }
    const host: BridgeHost = {}
    const loader = vi.fn(async (source: string, platform: 'telegram' | 'max') => {
      expect(platform).toBe('telegram')
      host.Telegram = { WebApp: telegram }
      expect(source).toBe(TELEGRAM_BRIDGE_SOURCE)
    })

    await expect(loadPlatformBridge({ host, hash: '#tgWebAppData=sensitive', loadScript: loader }))
      .resolves.toBe('telegram')
    expect(loader).toHaveBeenCalledOnce()
    expect(loader).not.toHaveBeenCalledWith(MAX_BRIDGE_SOURCE, 'max')
  })

  it('delegates Telegram lifecycle and returns exact init data', async () => {
    const bridge: TelegramWebAppBridge = {
      initData: 'telegram-raw',
      initDataUnsafe: { user: { id: 7, first_name: ' Роман ' } },
      ready: vi.fn(),
      expand: vi.fn(),
      close: vi.fn(),
      openLink: vi.fn(),
      openTelegramLink: vi.fn(),
    }
    const platform = createMiniAppPlatform({ Telegram: { WebApp: bridge } }, 'telegram')

    platform.ready()
    expect(platform.getInitData()).toBe('telegram-raw')
    expect(platform.getUser()).toEqual({ id: '7', firstName: 'Роман' })
    expect(bridge.ready).toHaveBeenCalledOnce()
    expect(bridge.expand).toHaveBeenCalledOnce()
    await platform.share({ text: 'Тест', url: 'https://example.test/item' })
    expect(bridge.openTelegramLink).toHaveBeenCalledOnce()
  })

  it('returns exact inner MAX WebAppData and uses native sharing', async () => {
    const bridge: MaxWebAppBridge = {
      initData: 'max-inner-data',
      shareContent: vi.fn(async () => undefined),
    }
    const platform = createMiniAppPlatform({ WebApp: bridge }, 'max')

    expect(platform.getInitData()).toBe('max-inner-data')
    expect(platform.canClose).toBe(false)
    expect(() => platform.ready()).not.toThrow()
    await platform.share({ text: 'Тест', url: 'https://example.test/item' })
    expect(bridge.shareContent).toHaveBeenCalledWith({ text: 'Тест', link: 'https://example.test/item' })
  })

  it('creates a Browser preview without init data', () => {
    const platform = createMiniAppPlatform({}, 'browser')
    expect(platform.kind).toBe('browser')
    expect(platform.getInitData()).toBe('')
  })
})
