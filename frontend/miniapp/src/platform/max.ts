import type { MaxWebAppBridge, RawMiniAppUser } from './bridgeTypes'
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

export class MaxMiniAppPlatform implements MiniAppPlatform {
  readonly kind = 'max' as const
  readonly #bridge: MaxWebAppBridge

  constructor(bridge: MaxWebAppBridge) {
    this.#bridge = bridge
  }

  get canClose(): boolean {
    return typeof this.#bridge.close === 'function'
  }

  getInitData(): string {
    // Это уже внутреннее WebAppData; внешний fragment backend не принимает.
    return this.#bridge.initData ?? ''
  }

  getUser(): MiniAppUser | null {
    return normalizedUser(this.#bridge.initDataUnsafe?.user)
  }

  ready(): void {
    // У MAX нет подтверждённого аналога Telegram.WebApp.ready/expand.
  }

  close(): void {
    // Метод зависит от версии клиента MAX, поэтому вызывается только при наличии.
    this.#bridge.close?.()
  }

  openLink(url: string): void {
    const target = safeExternalUrl(url)
    if (this.#bridge.openLink) {
      void this.#bridge.openLink(target)
      return
    }
    void this.#bridge.openMaxLink?.(target)
  }

  async share(payload: SharePayload): Promise<void> {
    const nativeShare = this.#bridge.shareMaxContent ?? this.#bridge.shareContent
    const sharePayload: { text: string; link?: string } = { text: payload.text }
    if (payload.url) sharePayload.link = safeExternalUrl(payload.url)

    if (nativeShare) {
      await nativeShare.call(this.#bridge, sharePayload)
      return
    }
    if (sharePayload.link) this.openLink(sharePayload.link)
  }
}
