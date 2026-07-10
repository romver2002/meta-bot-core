import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { BaseEdge, EdgeLabelRenderer, useReactFlow } from '@xyflow/react'

const clamp = (value, min, max) => Math.min(Math.max(value, min), max)

function edgeSide(id) {
  let value = 0
  for (const character of id) value = ((value * 31) + character.charCodeAt(0)) >>> 0
  return value % 2 === 0 ? 1 : -1
}

function defaultBend(id, sourceX, sourceY, targetX, targetY) {
  const deltaX = targetX - sourceX
  const deltaY = targetY - sourceY
  const distance = Math.hypot(deltaX, deltaY) || 1
  const magnitude = clamp(distance * 0.16, 34, 104) * edgeSide(id)

  return {
    x: (-deltaY / distance) * magnitude,
    y: (deltaX / distance) * magnitude,
  }
}

function pointOnQuadratic(sourceX, sourceY, controlX, controlY, targetX, targetY) {
  return {
    x: (sourceX + (2 * controlX) + targetX) / 4,
    y: (sourceY + (2 * controlY) + targetY) / 4,
  }
}

export default function AdaptiveEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  markerStart,
  markerEnd,
  label,
  data,
  style,
  selected,
  onBendChange,
}) {
  const { screenToFlowPosition } = useReactFlow()
  const [isDragging, setIsDragging] = useState(false)
  const cleanupDragRef = useRef(null)
  const midpointX = (sourceX + targetX) / 2
  const midpointY = (sourceY + targetY) / 2
  const fallbackBend = useMemo(
    () => defaultBend(id, sourceX, sourceY, targetX, targetY),
    [id, sourceX, sourceY, targetX, targetY],
  )
  const bend = data?.bend || fallbackBend
  const controlX = midpointX + bend.x
  const controlY = midpointY + bend.y
  const labelPosition = pointOnQuadratic(sourceX, sourceY, controlX, controlY, targetX, targetY)
  const path = `M ${sourceX},${sourceY} Q ${controlX},${controlY} ${targetX},${targetY}`
  const color = style?.stroke || '#64748B'

  const stopDragging = useCallback(() => {
    cleanupDragRef.current?.()
    setIsDragging(false)
    cleanupDragRef.current = null
  }, [])

  useEffect(() => () => cleanupDragRef.current?.(), [])

  const beginBendDrag = useCallback((event) => {
    if (event.button !== undefined && event.button !== 0) return
    if (!onBendChange) return

    event.preventDefault()
    event.stopPropagation()
    stopDragging()

    const start = { x: event.clientX, y: event.clientY }
    let dragStarted = false

    const updateBend = (clientX, clientY) => {
      const position = screenToFlowPosition({ x: clientX, y: clientY })
      onBendChange(id, {
        x: Math.round((position.x - midpointX) * 10) / 10,
        y: Math.round((position.y - midpointY) * 10) / 10,
      })
    }
    const cleanup = () => {
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerup', onPointerUp)
      window.removeEventListener('pointercancel', onPointerCancel)
    }
    const onPointerMove = (moveEvent) => {
      if (!dragStarted) {
        const distance = Math.hypot(moveEvent.clientX - start.x, moveEvent.clientY - start.y)
        if (distance < 4) return
        dragStarted = true
        setIsDragging(true)
      }
      updateBend(moveEvent.clientX, moveEvent.clientY)
    }
    const onPointerUp = () => stopDragging()
    const onPointerCancel = () => stopDragging()

    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
    window.addEventListener('pointercancel', onPointerCancel)
    cleanupDragRef.current = cleanup
  }, [id, midpointX, midpointY, onBendChange, screenToFlowPosition, stopDragging])

  const labelText = typeof label === 'string' ? label : ''
  const labelClassName = `adaptive-edge__label nodrag nopan ${isDragging ? 'adaptive-edge__label--dragging' : ''}`

  return (
    <>
      <BaseEdge
        path={path}
        markerStart={markerStart}
        markerEnd={markerEnd}
        style={{ ...style, stroke: color, strokeWidth: selected ? 2.8 : 2.2 }}
        className="adaptive-edge__path"
        interactionWidth={0}
      />
      <path
        d={path}
        fill="none"
        stroke="transparent"
        strokeWidth={28}
        className="adaptive-edge__route nopan"
        onPointerDown={beginBendDrag}
      />
      {labelText && (
        <EdgeLabelRenderer>
          <button
            className={labelClassName}
            type="button"
            style={{
              transform: `translate(-50%, -50%) translate(${labelPosition.x}px, ${labelPosition.y}px)`,
              '--edge-color': color,
              zIndex: selected || isDragging ? 4 : 2,
            }}
            onPointerDown={beginBendDrag}
            title={labelText}
            aria-label={`Изменить изгиб связи «${labelText}»`}
          >
            <span className="adaptive-edge__grip" aria-hidden="true">⠿</span>
            <span className="adaptive-edge__label-text">{label}</span>
          </button>
        </EdgeLabelRenderer>
      )}
    </>
  )
}
