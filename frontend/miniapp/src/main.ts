import './styles.css'

import { MiniAppApi } from './api/miniAppApi'
import { MiniAppController } from './app/bootstrap'
import { MiniAppConfigError, readMiniAppConfig } from './config'
import { createMiniAppPlatform, PlatformBridgeUnavailableError } from './platform/factory'
import { BridgeLoadError, loadPlatformBridge } from './platform/loadBridge'
import { mountMiniApp, renderStartupError } from './ui/render'

function startupMessage(error: unknown): string {
  if (
    error instanceof MiniAppConfigError
    || error instanceof BridgeLoadError
    || error instanceof PlatformBridgeUnavailableError
  ) return error.message
  return 'Mini App не удалось запустить. Откройте приложение заново из чата.'
}

async function start(root: HTMLElement): Promise<void> {
  const config = readMiniAppConfig(window.location.search, import.meta.env.VITE_API_BASE_URL ?? '')
  const detected = await loadPlatformBridge({ host: window, hash: window.location.hash })
  const platform = createMiniAppPlatform(window, detected)
  const controller = new MiniAppController(config.botId, platform, new MiniAppApi(config.apiBaseUrl))
  mountMiniApp(root, controller, platform.kind)
  await controller.start()
}

const root = document.querySelector<HTMLElement>('#app')
if (root) {
  void start(root).catch((error: unknown) => renderStartupError(root, startupMessage(error)))
}
