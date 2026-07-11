import PanelResizeHandle from './PanelResizeHandle.jsx'

// Живой JSON агрегата Flow — наглядно показывает: сценарий это ДАННЫЕ, не код.
export default function JsonDrawer({ flow, onClose, width, minWidth, maxWidth, onResize, onReset }) {
  return (
    <div className="jsonDrawer" id="flow-data-drawer" style={{ '--json-drawer-width': `${width}px` }}>
      <PanelResizeHandle
        side="right"
        value={width}
        min={minWidth}
        max={maxWidth}
        label="Изменить ширину панели данных Flow"
        controls="flow-data-drawer"
        onResize={onResize}
        onReset={onReset}
        className="panelResizer--json"
      />
      <div className="jsonDrawer__head">
        <span>Flow как данные (уходит на backend) →&nbsp; Flow Engine это интерпретирует</span>
        <button className="icon-btn" onClick={onClose} title="Закрыть">✕</button>
      </div>
      <pre className="jsonDrawer__body">{JSON.stringify(flow, null, 2)}</pre>
    </div>
  )
}
