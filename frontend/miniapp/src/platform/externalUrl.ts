export class UnsafeExternalUrlError extends Error {
  constructor() {
    super('Разрешены только безопасные HTTPS-ссылки.')
    this.name = 'UnsafeExternalUrlError'
  }
}

export function safeExternalUrl(value: string): string {
  let parsed: URL
  try {
    parsed = new URL(value)
  } catch {
    throw new UnsafeExternalUrlError()
  }
  if (parsed.protocol !== 'https:') {
    throw new UnsafeExternalUrlError()
  }
  return parsed.toString()
}
