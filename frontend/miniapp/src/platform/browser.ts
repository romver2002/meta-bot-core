import { safeExternalUrl } from './externalUrl'
import type { MiniAppPlatform, MiniAppUser, SharePayload } from './types'

export interface BrowserServices {
  close: () => void
  open: (url: string) => void
  share?: (payload: ShareData) => Promise<void>
}

export class BrowserMiniAppPlatform implements MiniAppPlatform {
  readonly kind = 'browser' as const
  readonly canClose = false
  readonly #services: BrowserServices

  constructor(services: BrowserServices) {
    this.#services = services
  }

  getInitData(): string {
    return ''
  }

  getUser(): MiniAppUser | null {
    return null
  }

  ready(): void {}

  close(): void {
    this.#services.close()
  }

  openLink(url: string): void {
    this.#services.open(safeExternalUrl(url))
  }

  async share(payload: SharePayload): Promise<void> {
    const data: ShareData = { text: payload.text }
    if (payload.url) data.url = safeExternalUrl(payload.url)
    if (this.#services.share) {
      await this.#services.share(data)
      return
    }
    if (data.url) this.#services.open(data.url)
  }
}
