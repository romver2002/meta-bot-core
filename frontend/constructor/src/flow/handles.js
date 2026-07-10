export const BUTTON_HANDLE_PREFIX = 'button:'

export function buttonHandleId(index) {
  return `${BUTTON_HANDLE_PREFIX}${index}`
}

export function buttonIndexFromHandle(handle) {
  if (typeof handle !== 'string' || !handle.startsWith(BUTTON_HANDLE_PREFIX)) return null
  const index = Number(handle.slice(BUTTON_HANDLE_PREFIX.length))
  return Number.isInteger(index) && index >= 0 ? index : null
}

export function isButtonHandle(handle) {
  return buttonIndexFromHandle(handle) !== null
}

export function isButtonEdge(edge) {
  return isButtonHandle(edge.sourceHandle)
}
