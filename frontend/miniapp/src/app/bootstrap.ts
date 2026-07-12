import { MiniAppApiError } from '../api/miniAppApi'
import type { MiniAppAuthResponse, MiniAppResultResponse } from '../api/miniAppApi'
import type { MiniAppPlatform } from '../platform/types'

export type MiniAppState =
  | { status: 'idle' }
  | { status: 'authenticating' }
  | { status: 'preview' }
  | { status: 'ready' }
  | { status: 'submitting' }
  | { status: 'submitted' }
  | { status: 'error'; stage: 'auth' | 'submit'; message: string }

export interface MiniAppApiPort {
  authenticate(botId: string, initData: string): Promise<MiniAppAuthResponse>
  submitResult(
    botId: string,
    initData: string,
    result: Record<string, unknown>,
  ): Promise<MiniAppResultResponse>
}

export type StateListener = (state: MiniAppState) => void

function safeErrorMessage(error: unknown): string {
  if (error instanceof MiniAppApiError) return error.message
  return 'Произошла непредвиденная ошибка. Повторите попытку.'
}

export class MiniAppController {
  readonly #botId: string
  readonly #platform: MiniAppPlatform
  readonly #api: MiniAppApiPort
  readonly #listeners = new Set<StateListener>()
  #state: MiniAppState = { status: 'idle' }

  constructor(botId: string, platform: MiniAppPlatform, api: MiniAppApiPort) {
    this.#botId = botId
    this.#platform = platform
    this.#api = api
  }

  get state(): MiniAppState {
    return this.#state
  }

  get canClose(): boolean {
    return this.#platform.canClose
  }

  subscribe(listener: StateListener): () => void {
    this.#listeners.add(listener)
    listener(this.#state)
    return () => this.#listeners.delete(listener)
  }

  async start(): Promise<void> {
    if (this.#state.status === 'authenticating' || this.#state.status === 'submitting') return
    this.#platform.ready()

    if (this.#platform.kind === 'browser') {
      this.#setState({ status: 'preview' })
      return
    }

    this.#setState({ status: 'authenticating' })
    const initData = this.#platform.getInitData()
    if (!initData.trim()) {
      this.#setState({
        status: 'error',
        stage: 'auth',
        message: 'Платформа не передала данные запуска. Откройте Mini App заново из чата.',
      })
      return
    }

    try {
      await this.#api.authenticate(this.#botId, initData)
      this.#setState({ status: 'ready' })
    } catch (error) {
      this.#setState({ status: 'error', stage: 'auth', message: safeErrorMessage(error) })
    }
  }

  async submit(): Promise<void> {
    const canSubmit = this.#state.status === 'ready'
      || (this.#state.status === 'error' && this.#state.stage === 'submit')
    if (!canSubmit) return

    this.#setState({ status: 'submitting' })
    const initData = this.#platform.getInitData()
    if (!initData.trim()) {
      this.#setState({
        status: 'error',
        stage: 'submit',
        message: 'Данные запуска недоступны. Откройте Mini App заново из чата.',
      })
      return
    }

    try {
      await this.#api.submitResult(this.#botId, initData, { action: 'confirmed' })
      this.#setState({ status: 'submitted' })
    } catch (error) {
      this.#setState({ status: 'error', stage: 'submit', message: safeErrorMessage(error) })
    }
  }

  async retry(): Promise<void> {
    if (this.#state.status !== 'error') return
    if (this.#state.stage === 'auth') await this.start()
    else await this.submit()
  }

  close(): void {
    if (this.#state.status === 'submitted' && this.#platform.canClose) this.#platform.close()
  }

  #setState(state: MiniAppState): void {
    this.#state = state
    for (const listener of this.#listeners) listener(state)
  }
}
