// Живой JSON агрегата Flow — наглядно показывает: сценарий это ДАННЫЕ, не код.
export default function JsonDrawer({ flow, onClose }) {
  return (
    <div className="jsonDrawer">
      <div className="jsonDrawer__head">
        <span>Flow как данные (уходит на backend) →&nbsp; Flow Engine это интерпретирует</span>
        <button className="icon-btn" onClick={onClose} title="Закрыть">✕</button>
      </div>
      <pre className="jsonDrawer__body">{JSON.stringify(flow, null, 2)}</pre>
    </div>
  )
}
