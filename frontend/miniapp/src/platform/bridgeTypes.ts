export interface RawMiniAppUser {
  id?: string | number
  first_name?: string
  firstName?: string
  last_name?: string
  lastName?: string
  username?: string
}

export interface TelegramWebAppBridge {
  initData?: string
  initDataUnsafe?: {
    user?: RawMiniAppUser
  }
  ready?: () => void
  expand?: () => void
  close?: () => void
  openLink?: (url: string) => void
  openTelegramLink?: (url: string) => void
}

export interface MaxWebAppBridge {
  initData?: string
  initDataUnsafe?: {
    user?: RawMiniAppUser
  }
  version?: string
  close?: () => void
  openLink?: (url: string) => void | Promise<void>
  openMaxLink?: (url: string) => void | Promise<void>
  shareContent?: (payload: { text: string; link?: string }) => void | Promise<void>
  shareMaxContent?: (payload: { text: string; link?: string }) => void | Promise<void>
}

export interface BridgeHost {
  Telegram?: {
    WebApp?: TelegramWebAppBridge
  }
  WebApp?: MaxWebAppBridge
}
