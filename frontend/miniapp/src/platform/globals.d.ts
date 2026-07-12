import type { MaxWebAppBridge, TelegramWebAppBridge } from './bridgeTypes'

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebAppBridge
    }
    WebApp?: MaxWebAppBridge
  }
}

export {}
