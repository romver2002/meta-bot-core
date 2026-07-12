import type { RawMiniAppUser, TelegramWebAppBridge } from './bridgeTypes'
import { safeExternalUrl } from './externalUrl'
import type { MiniAppPlatform, MiniAppUser, SharePayload } from './types'

function normalizedUser(raw: RawMiniAppUser | undefined): MiniAppUser | null {
  if (raw?.id === undefined || String(raw.id).trim() === '') return null

  const user: MiniAppUser = { id: String(raw.id) }
  const firstName = raw.first_name ?? raw.firstName
  const lastName = raw.last_name ?? raw.lastName
  if (firstName?.trim()) user.firstName = firstName.trim()
  if (lastName?.trim()) user.lastName = lastName.trim()
  if (raw.username?.trim()) user.username = raw.username.trim()
  return user
}

export class TelegramMiniAppPlatform implements MiniAppPlatform {
  readonly kind = 'telegram' as const
  readonly #bridge: TelegramWebAppBridge

  constructor(bridge: TelegramWebAppBridge) {
    this.#bridge = bridge
  }

  get canClose(): boolean {
    return typeof this.#bridge.close === 'function'
  }

  getInitData(): string {
    return this.#bridge.initData ?? ''
  }

  getUser(): MiniAppUser | null {
    return normalizedUser(this.#bridge.initDataUnsafe?.user)
  }

  ready(): void {
    this.#bridge.ready?.()
    this.#bridge.expand?.()
  }

  close(): void {
    this.#bridge.close?.()
  }

  openLink(url: string): void {
    this.#bridge.openLink?.(safeExternalUrl(url))
  }

  async share(payload: SharePayload): Promise<void> {
    const shareUrl = new URL('https://t.me/share/url')
    shareUrl.searchParams.set('text', payload.text)
    if (payload.url) shareUrl.searchParams.set('url', safeExternalUrl(payload.url))

    const target = shareUrl.toString()
    if (this.#bridge.openTelegramLink) {
      this.#bridge.openTelegramLink(target)
      return
    }
    this.#bridge.openLink?.(target)
  }
}
