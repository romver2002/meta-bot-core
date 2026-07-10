// Каталог конструктора должен совпадать с Flow Engine v1:
// src/domain/flow/value_objects.py + src/infrastructure/platforms/capabilities_v1.py.

export const PLATFORMS = {
  telegram: {
    id: 'telegram',
    label: 'Telegram',
    tint: '#229ED9',
    caps: ['text', 'buttons', 'ask', 'condition', 'mini_app', 'save', 'http', 'notify'],
  },
  max: {
    id: 'max',
    label: 'MAX',
    tint: '#5B5BF5',
    caps: ['text', 'buttons', 'ask', 'condition', 'mini_app', 'save', 'http', 'notify'],
  },
}

export const OUTCOME_LABELS = {
  next: 'дальше',
  true: 'да',
  false: 'нет',
  error: 'ошибка',
}

export const TRIGGERS = [
  {
    type: 'start',
    label: 'Команда /start',
    icon: '⚑',
    category: 'Как пользователь входит',
    hint: 'Пользователь запустил бота',
    configFields: [],
  },
  {
    type: 'text',
    label: 'Текст пользователя',
    icon: '✎',
    category: 'Как пользователь входит',
    hint: 'Точное совпадение входящего сообщения',
    configFields: [
      { key: 'pattern', label: 'Текст / паттерн', kind: 'text', placeholder: 'меню' },
    ],
  },
  {
    type: 'callback',
    label: 'Нажатие кнопки',
    icon: '↳',
    category: 'Как пользователь входит',
    hint: 'Callback payload от inline-кнопки',
    configFields: [
      { key: 'payload', label: 'Payload', kind: 'text', placeholder: 'n_menu' },
    ],
  },
  {
    type: 'mini_app_result',
    label: 'Результат mini app',
    icon: '▣',
    category: 'Как пользователь входит',
    hint: 'Mini app вернул данные после проверки init data',
    configFields: [],
  },
]

export const TRIGGER_BY_TYPE = Object.fromEntries(TRIGGERS.map((t) => [t.type, t]))

export const BLOCKS = [
  {
    type: 'send_message',
    label: 'Отправить сообщение',
    icon: '●',
    color: '#2563EB',
    cap: 'text',
    category: 'Что отвечает бот',
    hint: 'Текст с переменными сценария',
    outputs: ['next'],
    fields: [
      { key: 'text', label: 'Текст сообщения', kind: 'textarea', required: true, placeholder: 'Здравствуйте, {name}.' },
    ],
  },
  {
    type: 'show_buttons',
    label: 'Сообщение с кнопками',
    icon: '▦',
    color: '#4F46E5',
    cap: 'buttons',
    category: 'Что отвечает бот',
    hint: 'Текст + кнопки Button. Переходы задаются target у каждой кнопки.',
    outputs: [],
    fields: [
      { key: 'text', label: 'Текст', kind: 'textarea', required: true, placeholder: 'Выберите действие:' },
      { key: 'buttons', label: 'Кнопки', kind: 'buttons' },
    ],
  },
  {
    type: 'ask',
    label: 'Задать вопрос и ждать',
    icon: '?',
    color: '#D97706',
    cap: 'ask',
    category: 'Логика и данные',
    hint: 'Задаёт вопрос, ждёт ответ пользователя и сохраняет его в переменную',
    outputs: ['next'],
    fields: [
      { key: 'prompt', label: 'Вопрос', kind: 'textarea', required: true, placeholder: 'Как к вам обращаться?' },
      { key: 'save_as', label: 'Переменная', kind: 'text', required: true, placeholder: 'req_name' },
    ],
  },
  {
    type: 'condition',
    label: 'Развилка',
    icon: '◇',
    color: '#9333EA',
    cap: 'condition',
    category: 'Логика и данные',
    hint: 'Ветвление по переменным сценария',
    outputs: ['true', 'false'],
    fields: [
      { key: 'expression', label: 'Условие', kind: 'text', required: true, placeholder: 'ai_answer' },
    ],
  },
  {
    type: 'open_mini_app',
    label: 'Открыть mini app',
    icon: '▤',
    color: '#0D9488',
    cap: 'mini_app',
    category: 'Mini app',
    hint: 'Показывает кнопку запуска mini app, привязанного к боту через API конструктора',
    outputs: ['next'],
    fields: [
      { key: 'text', label: 'Текст перед кнопкой', kind: 'textarea', placeholder: 'Откройте витрину внутри мессенджера.' },
      { key: 'button_text', label: 'Текст кнопки', kind: 'text', required: true, placeholder: 'Открыть' },
      { key: 'save_as', label: 'Куда сохранить результат', kind: 'text', placeholder: 'mini_app_result' },
    ],
  },
  {
    type: 'save',
    label: 'Сохранить значение',
    icon: '◆',
    color: '#475569',
    cap: 'save',
    category: 'Логика и данные',
    hint: 'Записывает значение в переменные активной сессии',
    outputs: ['next'],
    fields: [
      { key: 'key', label: 'Ключ', kind: 'text', required: true, placeholder: 'lead_source' },
      { key: 'value', label: 'Значение', kind: 'text', placeholder: '{answer}' },
    ],
  },
  {
    type: 'http_request',
    label: 'Запрос к API',
    icon: '⌁',
    color: '#0891B2',
    cap: 'http',
    category: 'Интеграции',
    hint: 'Внешний HTTP-вызов. Секреты указываются как {{secret:name}} и подставляются backend-портом.',
    outputs: ['next', 'error'],
    fields: [
      { key: 'method', label: 'Метод', kind: 'select', defaultValue: 'POST', options: [
        { v: 'GET', l: 'GET' },
        { v: 'POST', l: 'POST' },
        { v: 'PUT', l: 'PUT' },
        { v: 'PATCH', l: 'PATCH' },
        { v: 'DELETE', l: 'DELETE' },
      ] },
      { key: 'url', label: 'URL', kind: 'text', required: true, placeholder: 'https://api.example.com/ask' },
      { key: 'headers', label: 'Заголовки JSON', kind: 'json', jsonType: 'object', defaultValue: '{\n  "Content-Type": "application/json"\n}' },
      { key: 'body', label: 'Тело JSON', kind: 'json', jsonType: 'any', defaultValue: '{\n  "q": "{user_question}"\n}' },
      { key: 'timeout', label: 'Timeout, сек', kind: 'number', defaultValue: 10, min: 1, max: 60 },
      { key: 'response_map', label: 'Ответ → переменные', kind: 'json', jsonType: 'object', defaultValue: '{\n  "answer": "choices.0.message.content"\n}' },
    ],
  },
  {
    type: 'notify',
    label: 'Уведомить команду',
    icon: '↗',
    color: '#C2410C',
    cap: 'notify',
    category: 'Интеграции',
    hint: 'Отправляет сообщение адресату по роли. Адрес роли настраивается отдельно и не попадает в сценарий.',
    outputs: ['next'],
    fields: [
      { key: 'to', label: 'Роль адресата', kind: 'text', required: true, placeholder: 'sales' },
      { key: 'text', label: 'Текст уведомления', kind: 'textarea', required: true, placeholder: 'Новая заявка от {name}: {request}' },
    ],
  },
]

export const SOON_BLOCKS = [
  {
    type: 'custom_code',
    label: 'Python в песочнице',
    icon: '▰',
    color: '#E11D48',
    cap: 'code',
    hint: 'Есть в доменной модели, но не входит в Engine v1 capabilities. Вернётся после этапа sandbox.',
    sandbox: true,
  },
  {
    type: 'payment',
    label: 'Оплата',
    icon: '₽',
    color: '#7C3AED',
    cap: 'payment',
    hint: 'Платёжный блок вынесен за MVP: механики Telegram и MAX различаются.',
  },
]

export const BLOCK_BY_TYPE = Object.fromEntries(
  [...BLOCKS, ...SOON_BLOCKS].map((b) => [b.type, b]),
)

export function blockAvailable(block, platformId) {
  const platform = PLATFORMS[platformId]
  if (!platform) return true
  return block.cap ? platform.caps.includes(block.cap) : true
}

export function makeDefaultParams(type) {
  const def = BLOCK_BY_TYPE[type]
  return Object.fromEntries((def?.fields || []).map((field) => {
    if (field.kind === 'buttons') return [field.key, []]
    if (field.defaultValue !== undefined) return [field.key, field.defaultValue]
    return [field.key, '']
  }))
}
