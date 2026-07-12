export type MiniAppPlatformKind = 'telegram' | 'max' | 'browser'

/** Данные из client bridge недоверенные и годятся только для оформления UI. */
export interface MiniAppUser {
  id: string
  firstName?: string
  lastName?: string
  username?: string
}

export interface SharePayload {
  text: string
  url?: string
}

/** Граница общего runtime и платформенных JS bridge (ADR-0006). */
export interface MiniAppPlatform {
  readonly kind: MiniAppPlatformKind
  readonly canClose: boolean
  getInitData(): string
  getUser(): MiniAppUser | null
  ready(): void
  close(): void
  openLink(url: string): void
  share(payload: SharePayload): Promise<void>
}
