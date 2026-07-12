import type { MiniAppController, MiniAppState } from '../app/bootstrap'
import type { MiniAppPlatformKind } from '../platform/types'

interface StateCopy {
  eyebrow: string
  title: string
  message: string
  tone: 'calm' | 'busy' | 'success' | 'error'
}

function element<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag)
  node.className = className
  if (text !== undefined) node.textContent = text
  return node
}

function platformLabel(platform: MiniAppPlatformKind): string {
  if (platform === 'telegram') return 'Telegram'
  if (platform === 'max') return 'MAX'
  return 'Browser preview'
}

function stateCopy(state: MiniAppState): StateCopy {
  if (state.status === 'idle' || state.status === 'authenticating') {
    return {
      eyebrow: 'Безопасный вход',
      title: 'Готовим рабочее пространство',
      message: 'Проверяем запуск и защищённое соединение с сервисом.',
      tone: 'busy',
    }
  }
  if (state.status === 'preview') {
    return {
      eyebrow: 'Режим дизайна',
      title: 'Быстрый предпросмотр',
      message: 'Интерфейс готов. Авторизация включится внутри Telegram или MAX.',
      tone: 'calm',
    }
  }
  if (state.status === 'ready') {
    return {
      eyebrow: 'Запуск подтверждён',
      title: 'Всё готово к действию',
      message: 'Передайте результат сценарию одним нажатием.',
      tone: 'calm',
    }
  }
  if (state.status === 'submitting') {
    return {
      eyebrow: 'Защищённая отправка',
      title: 'Фиксируем результат',
      message: 'Операция займёт всего несколько мгновений.',
      tone: 'busy',
    }
  }
  if (state.status === 'submitted') {
    return {
      eyebrow: 'Операция завершена',
      title: 'Результат передан',
      message: 'Данные уже в сценарии. Можно возвращаться в чат.',
      tone: 'success',
    }
  }
  return {
    eyebrow: 'Нужно внимание',
    title: 'Попробуем ещё раз',
    message: state.message,
    tone: 'error',
  }
}

function stateContent(state: MiniAppState, controller: MiniAppController): DocumentFragment {
  const fragment = document.createDocumentFragment()
  const copy = stateCopy(state)
  const statusIcon = element('span', `status-icon status-icon--${copy.tone}`)
  statusIcon.setAttribute('aria-hidden', 'true')
  const heading = element('div', 'status-heading')
  heading.append(
    element('span', 'status-eyebrow', copy.eyebrow),
    element('h1', 'app-title', copy.title),
  )
  const message = element('p', `status-message${copy.tone === 'error' ? ' error-message' : ''}`, copy.message)
  if (copy.tone === 'error') message.setAttribute('role', 'alert')
  fragment.append(statusIcon, heading, message)

  if (state.status === 'idle' || state.status === 'authenticating') {
    return fragment
  }
  if (state.status === 'preview') {
    return fragment
  }
  if (state.status === 'ready') {
    const button = element('button', 'primary-button', 'Подтвердить действие')
    button.type = 'button'
    button.addEventListener('click', () => { void controller.submit() })
    fragment.append(button)
    return fragment
  }
  if (state.status === 'submitting') {
    const button = element('button', 'primary-button', 'Отправляем…')
    button.type = 'button'
    button.disabled = true
    fragment.append(button)
    return fragment
  }
  if (state.status === 'submitted') {
    if (controller.canClose) {
      const button = element('button', 'primary-button', 'Вернуться в чат')
      button.type = 'button'
      button.addEventListener('click', () => controller.close())
      fragment.append(button)
    }
    return fragment
  }

  const button = element('button', 'secondary-button', 'Повторить')
  button.type = 'button'
  button.addEventListener('click', () => { void controller.retry() })
  fragment.append(button)
  return fragment
}

export function mountMiniApp(
  root: HTMLElement,
  controller: MiniAppController,
  platform: MiniAppPlatformKind,
): () => void {
  return controller.subscribe((state) => {
    const card = element('section', 'app-card')
    card.dataset.platform = platform
    card.setAttribute('aria-busy', String(state.status === 'authenticating' || state.status === 'submitting'))
    const brand = element('header', 'brand-row')
    const brandIdentity = element('div', 'brand-identity')
    brandIdentity.append(
      element('span', 'brand-mark', 'M'),
      element('span', 'brand-name', 'Meta Mini App'),
    )
    brand.append(brandIdentity, element('span', 'platform-badge', platformLabel(platform)))
    const progress = element('div', 'progress-track')
    progress.append(element('span', 'progress-value'))
    card.append(
      progress,
      brand,
      stateContent(state, controller),
    )
    root.replaceChildren(card)
  })
}

export function renderStartupError(root: HTMLElement, message: string): void {
  const card = element('section', 'app-card')
  card.append(
    element('span', 'brand-mark', 'M'),
    element('span', 'status-eyebrow', 'Ошибка запуска'),
    element('h1', 'app-title', 'Не удалось открыть Mini App'),
    element('p', 'status-message error-message', message),
  )
  root.replaceChildren(card)
}
