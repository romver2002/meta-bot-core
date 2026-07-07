// ─────────────────────────────────────────────────────────────────────────
// Каталог триггеров и блоков конструктора meta-bot-core.
//
// ВАЖНО: узел на холсте — это ДАННЫЕ ({ type, params }), а НЕ код.
// Источник истины по типам — memory-bank/domain/flow-blocks.md.
// Различия платформ выражаются данными (CapabilityMatrix), без if platform==.
// ─────────────────────────────────────────────────────────────────────────

// Платформы и их возможности (заглушка CapabilityMatrix — на проде приходит с backend).
export const PLATFORMS = {
  telegram: {
    id: 'telegram',
    label: 'Telegram',
    tint: '#229ED9',
    caps: ['text', 'buttons', 'ask', 'condition', 'mini_app', 'save', 'http', 'code'],
  },
  max: {
    id: 'max',
    label: 'MAX',
    tint: '#5B5BF5',
    // mini app в MAX существует только внутри чат-бота (BR-003) — здесь возможность есть.
    caps: ['text', 'buttons', 'ask', 'condition', 'mini_app', 'save', 'http', 'code'],
  },
}

// 4 триггера входа в сценарий.
export const TRIGGERS = [
  { type: 'start',            label: 'Команда /start',            icon: '⚑',  hint: 'Пользователь запустил бота' },
  { type: 'text',             label: 'Пользователь написал…',      icon: '✍️', hint: 'Входящее текстовое сообщение (точное совпадение или паттерн)' },
  { type: 'callback',         label: 'Нажал кнопку',               icon: '👆', hint: 'Нажатие inline-кнопки (событие ButtonClicked)' },
  { type: 'mini_app_result',  label: 'Mini app вернул результат',  icon: '📲', hint: 'Mini app прислал результат (после валидации init data, BR-007)' },
]

// 8 блоков-узлов. cap — требуемая возможность платформы. fields — поля панели настройки.
export const BLOCKS = [
  {
    type: 'send_message', label: 'Отправить сообщение', icon: '💬', color: '#2563EB', cap: 'text',
    hint: 'Текст с переменными сценария', outputs: ['next'],
    fields: [
      { key: 'text', label: 'Текст сообщения', kind: 'textarea', placeholder: 'Привет, {name}! 👋' },
      { key: 'attachment', label: 'Вложение (URL, опц.)', kind: 'text', placeholder: 'https://…' },
    ],
  },
  {
    type: 'show_buttons', label: 'Сообщение с кнопками', icon: '🔘', color: '#4F46E5', cap: 'buttons',
    hint: 'Текст + кнопки Button', outputs: ['next'],
    fields: [
      { key: 'text', label: 'Текст', kind: 'textarea', placeholder: 'Выберите действие:' },
      { key: 'buttons', label: 'Кнопки', kind: 'buttons' },
    ],
  },
  {
    type: 'ask', label: 'Задать вопрос и ждать', icon: '❓', color: '#D97706', cap: 'ask',
    hint: 'Ждёт ответ, сохраняет в переменную (переводит Session-FSM в ожидание)', outputs: ['next'],
    fields: [
      { key: 'prompt', label: 'Вопрос', kind: 'textarea', placeholder: 'Как вас зовут?' },
      { key: 'save_as', label: 'Сохранить ответ в переменную', kind: 'text', placeholder: 'name' },
      { key: 'validation', label: 'Проверка ответа', kind: 'select', options: [
        { v: 'none', l: 'без проверки' }, { v: 'number', l: 'число' },
        { v: 'email', l: 'email' }, { v: 'phone', l: 'телефон' },
      ] },
    ],
  },
  {
    type: 'condition', label: 'Развилка «Если…»', icon: '◇', color: '#9333EA', cap: 'condition',
    hint: 'Ветвление по переменным: да / нет', outputs: ['true', 'false'],
    fields: [
      { key: 'expression', label: 'Условие', kind: 'text', placeholder: 'age >= 18' },
    ],
  },
  {
    type: 'open_mini_app', label: 'Открыть mini app', icon: '📱', color: '#0D9488', cap: 'mini_app',
    hint: 'Кнопка запуска mini app бота (результат вернётся триггером mini_app_result)', outputs: ['next'],
    fields: [
      { key: 'mini_app', label: 'Mini app', kind: 'select', options: [
        { v: '', l: '— выбрать —' }, { v: 'catalog', l: 'Каталог' }, { v: 'booking', l: 'Запись' },
      ] },
      { key: 'button_text', label: 'Текст кнопки', kind: 'text', placeholder: 'Открыть' },
    ],
  },
  {
    type: 'save', label: 'Сохранить значение', icon: '💾', color: '#475569', cap: 'save',
    hint: 'Записать в состояние сессии', outputs: ['next'],
    fields: [
      { key: 'key', label: 'Ключ', kind: 'text', placeholder: 'lead_source' },
      { key: 'value', label: 'Значение', kind: 'text', placeholder: '{answer}' },
    ],
  },
  {
    type: 'http_request', label: 'Запрос к API', icon: '🌐', color: '#0891B2', cap: 'http',
    hint: 'Внешний HTTP-вызов, ответ → переменные', outputs: ['next'],
    fields: [
      { key: 'method', label: 'Метод', kind: 'select', options: [
        { v: 'GET', l: 'GET' }, { v: 'POST', l: 'POST' }, { v: 'PUT', l: 'PUT' }, { v: 'DELETE', l: 'DELETE' },
      ] },
      { key: 'url', label: 'URL', kind: 'text', placeholder: 'https://api.example.com/lead' },
      { key: 'headers', label: 'Заголовки (JSON)', kind: 'textarea', placeholder: '{"Content-Type": "application/json"}' },
      { key: 'response_map', label: 'Ответ → переменные', kind: 'text', placeholder: 'lead_id = data.id' },
    ],
  },
  {
    type: 'custom_code', label: 'Python в песочнице', icon: '🔒', color: '#E11D48', cap: 'code',
    hint: '10–20% логики: чистая функция run(context)→dict в изоляции (BR-004)', outputs: ['next'],
    sandbox: true,
    fields: [
      { key: 'code', label: 'Код (Python)', kind: 'code', placeholder: 'def run(context):\n    return {"ok": True}' },
      { key: 'input_mapping', label: 'Вход (context ←)', kind: 'text', placeholder: 'name = user_name' },
      { key: 'output_mapping', label: 'Выход (→ переменные)', kind: 'text', placeholder: 'greeting = result.text' },
    ],
  },
]

// «Скоро / вне MVP» — демонстрирует приглушение по CapabilityMatrix (BR-006).
export const SOON_BLOCKS = [
  { type: 'payment', label: 'Оплата', icon: '💳', color: '#7C3AED', cap: 'payment',
    hint: 'Платёж в сценарии — вынесено за MVP (roadmap); механики Telegram и MAX различаются' },
]

export const BLOCK_BY_TYPE = Object.fromEntries(
  [...BLOCKS, ...SOON_BLOCKS].map((b) => [b.type, b]),
)

// Доступен ли блок на платформе (единственная точка «различия платформ» — и то по данным).
export function blockAvailable(block, platformId) {
  const platform = PLATFORMS[platformId]
  if (!platform) return true
  return block.cap ? platform.caps.includes(block.cap) : true
}
