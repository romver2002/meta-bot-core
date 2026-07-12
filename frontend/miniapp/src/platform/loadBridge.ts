import type { BridgeHost } from './bridgeTypes'
import type { MiniAppPlatformKind } from './types'

export const TELEGRAM_BRIDGE_SOURCE = 'https://telegram.org/js/telegram-web-app.js'
export const MAX_BRIDGE_SOURCE = 'https://st.max.ru/js/max-web-app.js'

type EmbeddedPlatform = Exclude<MiniAppPlatformKind, 'browser'>

export class BridgeLoadError extends Error {
  constructor(message = 'Не удалось подключить платформенный Mini App bridge.') {
    super(message)
    this.name = 'BridgeLoadError'
  }
}

export type BridgeScriptLoader = (source: string, platform: EmbeddedPlatform) => Promise<void>

const TELEGRAM_LAUNCH_MARKER = /(?:^|&)(?:tgWebAppData|tgWebAppVersion|tgWebAppPlatform)=/
const MAX_LAUNCH_MARKER = /(?:^|&)(?:WebAppData|WebAppVersion|WebAppPlatform)=/

function fragmentWithoutHash(hash: string): string {
  return hash.startsWith('#') ? hash.slice(1) : hash
}

/** Определяет среду, не извлекая и не сохраняя само значение init data. */
export function detectLaunchPlatform(host: BridgeHost, hash: string): MiniAppPlatformKind {
  const hasTelegramData = Boolean(host.Telegram?.WebApp?.initData)
  const hasMaxData = Boolean(host.WebApp?.initData)
  if (hasTelegramData && hasMaxData) {
    throw new BridgeLoadError('Обнаружены конфликтующие платформенные bridge.')
  }
  if (hasTelegramData) return 'telegram'
  if (hasMaxData) return 'max'

  const fragment = fragmentWithoutHash(hash)
  const hasTelegramMarker = TELEGRAM_LAUNCH_MARKER.test(fragment)
  const hasMaxMarker = MAX_LAUNCH_MARKER.test(fragment)
  if (hasTelegramMarker && hasMaxMarker) {
    throw new BridgeLoadError('Обнаружены конфликтующие параметры запуска Mini App.')
  }
  if (hasTelegramMarker) return 'telegram'
  if (hasMaxMarker) return 'max'
  return 'browser'
}

function officialSource(platform: EmbeddedPlatform): string {
  return platform === 'telegram' ? TELEGRAM_BRIDGE_SOURCE : MAX_BRIDGE_SOURCE
}

function bridgeAvailable(host: BridgeHost, platform: EmbeddedPlatform): boolean {
  return platform === 'telegram' ? Boolean(host.Telegram?.WebApp) : Boolean(host.WebApp)
}

export function loadOfficialBridgeScript(
  source: string,
  platform: EmbeddedPlatform,
  documentRef: Document = document,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const script = documentRef.createElement('script')
    script.src = source
    script.async = true
    script.dataset.miniAppBridge = platform

    const timeout = globalThis.setTimeout(() => {
      script.remove()
      reject(new BridgeLoadError())
    }, 10_000)

    script.addEventListener('load', () => {
      globalThis.clearTimeout(timeout)
      resolve()
    }, { once: true })
    script.addEventListener('error', () => {
      globalThis.clearTimeout(timeout)
      script.remove()
      reject(new BridgeLoadError())
    }, { once: true })
    documentRef.head.append(script)
  })
}

export interface LoadPlatformBridgeOptions {
  host: BridgeHost
  hash: string
  loadScript?: BridgeScriptLoader
}

/** Загружает только bridge платформы, заявленной launch-параметрами. */
export async function loadPlatformBridge(options: LoadPlatformBridgeOptions): Promise<MiniAppPlatformKind> {
  const platform = detectLaunchPlatform(options.host, options.hash)
  if (platform === 'browser') return platform
  if (bridgeAvailable(options.host, platform)) return platform

  const loadScript = options.loadScript ?? loadOfficialBridgeScript
  await loadScript(officialSource(platform), platform)
  if (!bridgeAvailable(options.host, platform)) throw new BridgeLoadError()
  return platform
}
