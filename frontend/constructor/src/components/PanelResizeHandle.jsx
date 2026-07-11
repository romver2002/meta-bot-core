import { useCallback, useEffect, useRef, useState } from 'react'

export default function PanelResizeHandle({
  side,
  value,
  min,
  max,
  label,
  controls,
  onResize,
  onReset,
  className = '',
}) {
  const [isDragging, setIsDragging] = useState(false)
  const cleanupDragRef = useRef(null)
  const direction = side === 'left' ? 1 : -1

  const stopDragging = useCallback(() => {
    cleanupDragRef.current?.()
    cleanupDragRef.current = null
    setIsDragging(false)
  }, [])

  useEffect(() => () => cleanupDragRef.current?.(), [])

  const beginResize = useCallback((event) => {
    if (event.button !== undefined && event.button !== 0) return
    event.preventDefault()
    event.stopPropagation()
    stopDragging()
    setIsDragging(true)

    const startX = event.clientX
    const startWidth = value
    const cleanup = () => {
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerup', onPointerUp)
      window.removeEventListener('pointercancel', onPointerCancel)
    }
    const onPointerMove = (moveEvent) => onResize(startWidth + (moveEvent.clientX - startX) * direction)
    const onPointerUp = () => stopDragging()
    const onPointerCancel = () => stopDragging()

    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
    window.addEventListener('pointercancel', onPointerCancel)
    cleanupDragRef.current = cleanup
  }, [direction, onResize, stopDragging, value])

  const onKeyDown = useCallback((event) => {
    const step = event.shiftKey ? 40 : 12
    if (event.key === 'ArrowLeft') {
      event.preventDefault()
      onResize(value - step * direction)
    }
    if (event.key === 'ArrowRight') {
      event.preventDefault()
      onResize(value + step * direction)
    }
    if (event.key === 'Home') {
      event.preventDefault()
      onResize(min)
    }
    if (event.key === 'End') {
      event.preventDefault()
      onResize(max)
    }
  }, [direction, max, min, onResize, value])

  return (
    <div
      className={`panelResizer ${isDragging ? 'panelResizer--dragging' : ''} ${className}`}
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-controls={controls}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuenow={value}
      aria-valuetext={`${value} пикселей`}
      tabIndex={0}
      title="Перетащите границу. Стрелки меняют ширину, Shift — крупный шаг, двойной щелчок сбрасывает её."
      onPointerDown={beginResize}
      onKeyDown={onKeyDown}
      onDoubleClick={onReset}
    />
  )
}
