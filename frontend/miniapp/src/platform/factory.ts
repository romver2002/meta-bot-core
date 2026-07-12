import type { BridgeHost } from './bridgeTypes'
import { BrowserMiniAppPlatform } from './browser'
import { MaxMiniAppPlatform } from './max'
import { TelegramMiniAppPlatform } from './telegram'
import type { MiniAppPlatform, MiniAppPlatformKind } from './types'

export class PlatformBridgeUnavailableError extends Error {
  constructor() {
    super('Платформенный Mini App bridge недоступен. Откройте приложение заново из чата.')
    this.name = 'PlatformBridgeUnavailableError'
  }
}

export interface PlatformHost extends BridgeHost {
  open?: (url?: string | URL, target?: string, features?: string) => WindowProxy | null
  close?: () => void
  navigator?: {
    share?: (data?: ShareData) => Promise<void>
  }
}

function browserPlatform(host: PlatformHost): BrowserMiniAppPlatform {
  const services = {
    close: () => host.close?.(),
    open: (url: string) => {
      host.open?.(url, '_blank', 'noopener,noreferrer')
    },
    ...(host.navigator?.share
      ? { share: (payload: ShareData) => host.navigator?.share?.(payload) ?? Promise.resolve() }
      : {}),
  }
  return new BrowserMiniAppPlatform(services)
}

/** Единственная точка выбора platform bridge во frontend runtime. */
export function createMiniAppPlatform(host: PlatformHost, expected: MiniAppPlatformKind): MiniAppPlatform {
  if (expected === 'telegram') {
    const bridge = host.Telegram?.WebApp
    if (!bridge) throw new PlatformBridgeUnavailableError()
    return new TelegramMiniAppPlatform(bridge)
  }
  if (expected === 'max') {
    const bridge = host.WebApp
    if (!bridge) throw new PlatformBridgeUnavailableError()
    return new MaxMiniAppPlatform(bridge)
  }
  return browserPlatform(host)
}
