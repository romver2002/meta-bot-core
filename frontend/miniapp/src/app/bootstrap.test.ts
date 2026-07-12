import { describe, expect, it, vi } from 'vitest'

import type { MiniAppApiPort } from './bootstrap'
import { MiniAppController } from './bootstrap'
import type { MiniAppPlatform } from '../platform/types'

const BOT_ID = '0123456789abcdef0123456789abcdef'
const INIT_DATA = 'auth_date=1&hash=sensitive'

function platform(kind: MiniAppPlatform['kind'] = 'telegram'): MiniAppPlatform {
  return {
    kind,
    canClose: kind === 'telegram',
    getInitData: () => kind === 'browser' ? '' : INIT_DATA,
    getUser: () => null,
    ready: vi.fn(),
    close: vi.fn(),
    openLink: vi.fn(),
    share: vi.fn(async () => undefined),
  }
}

function api(): MiniAppApiPort {
  return {
    authenticate: vi.fn(async () => ({ external_user_id: '777' })),
    submitResult: vi.fn(async () => ({ ok: true as const })),
  }
}

describe('MiniAppController', () => {
  it('authenticates before enabling result submission without retaining init data in state', async () => {
    const bridge = platform()
    const client = api()
    const controller = new MiniAppController(BOT_ID, bridge, client)

    await controller.start()

    expect(client.authenticate).toHaveBeenCalledWith(BOT_ID, INIT_DATA)
    expect(controller.state).toEqual({ status: 'ready' })
    expect(JSON.stringify(controller.state)).not.toContain(INIT_DATA)
  })

  it('keeps Browser adapter in preview and never calls backend', async () => {
    const client = api()
    const controller = new MiniAppController(BOT_ID, platform('browser'), client)

    await controller.start()

    expect(controller.state).toEqual({ status: 'preview' })
    expect(client.authenticate).not.toHaveBeenCalled()
  })

  it('submits only the explicit result and closes only after success', async () => {
    const bridge = platform()
    const client = api()
    const controller = new MiniAppController(BOT_ID, bridge, client)

    controller.close()
    expect(bridge.close).not.toHaveBeenCalled()
    await controller.start()
    await controller.submit()

    expect(client.submitResult).toHaveBeenCalledWith(BOT_ID, INIT_DATA, { action: 'confirmed' })
    expect(controller.state).toEqual({ status: 'submitted' })
    controller.close()
    expect(bridge.close).toHaveBeenCalledOnce()
  })

  it('blocks duplicate submission while a request is running', async () => {
    let release: (() => void) | undefined
    const pending = new Promise<void>((resolve) => { release = resolve })
    const client = api()
    client.submitResult = vi.fn(async () => {
      await pending
      return { ok: true as const }
    })
    const controller = new MiniAppController(BOT_ID, platform(), client)
    await controller.start()

    const first = controller.submit()
    const second = controller.submit()
    expect(client.submitResult).toHaveBeenCalledOnce()
    release?.()
    await Promise.all([first, second])
  })
})
