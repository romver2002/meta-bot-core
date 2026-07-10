import { Component } from 'react'

export default class AppErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="appError" role="alert">
          <div className="appError__card">
            <div className="appError__icon" aria-hidden="true">⚠</div>
            <h1>Конструктор не удалось отобразить</h1>
            <p>Черновик в браузере не изменён. Обновите страницу и повторите действие.</p>
            <button className="btn btn--primary" type="button" onClick={() => window.location.reload()}>
              Обновить страницу
            </button>
          </div>
        </main>
      )
    }

    return this.props.children
  }
}
