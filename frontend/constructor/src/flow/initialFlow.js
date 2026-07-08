import { MarkerType } from '@xyflow/react'

const arrow = { markerEnd: { type: MarkerType.ArrowClosed } }
const yes = { style: { stroke: '#16A34A' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#16A34A' } }
const no = { style: { stroke: '#64748B' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#64748B' } }
const error = { style: { stroke: '#DC2626' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#DC2626' } }

export const initialNodes = [
  {
    id: 't_start', type: 'trigger', position: { x: 420, y: 0 },
    data: { group: 'trigger', type: 'start', label: 'Команда /start', icon: '⚑', config: {} },
  },
  {
    id: 't_menu', type: 'trigger', position: { x: 140, y: 0 },
    data: { group: 'trigger', type: 'callback', label: 'Нажатие кнопки', icon: '↳', config: { payload: 'n_menu' } },
  },
  {
    id: 't_mini_result', type: 'trigger', position: { x: 720, y: 0 },
    data: { group: 'trigger', type: 'mini_app_result', label: 'Результат mini app', icon: '▣', config: {} },
  },

  {
    id: 'n_greet', type: 'block', position: { x: 420, y: 130 },
    data: { group: 'block', type: 'send_message', params: {
      text: 'Здравствуйте! Я — умный помощник. Помогу разобраться в услугах, отвечу на вопросы и приму заявку.',
      attachment: '',
    } },
  },
  {
    id: 'n_menu', type: 'block', position: { x: 420, y: 280 },
    data: { group: 'block', type: 'show_buttons', params: {
      text: 'Главное меню — чем помочь?',
      buttons: [
        { label: 'Задать вопрос', action: 'next', target: 'n_ask_prompt' },
        { label: 'Открыть mini app', action: 'next', target: 'n_open_app' },
        { label: 'Оставить заявку', action: 'next', target: 'req_start' },
        { label: 'Связаться с разработчиком', action: 'next', target: 'dev_start' },
        { label: 'Сайт', action: 'url', target: 'https://example.com' },
      ],
    } },
  },

  {
    id: 'n_ask_prompt', type: 'block', position: { x: 40, y: 460 },
    data: { group: 'block', type: 'ask', params: {
      prompt: 'Напишите вопрос одним сообщением — отвечу по базе знаний.',
      save_as: 'user_question',
      validation: '',
    } },
  },
  {
    id: 'n_ai', type: 'block', position: { x: 40, y: 620 },
    data: { group: 'block', type: 'http_request', params: {
      method: 'POST',
      url: 'https://openrouter.ai/api/v1/chat/completions',
      headers: '{\n  "Authorization": "Bearer {{secret:openrouter_api_key}}",\n  "Content-Type": "application/json"\n}',
      body: '{\n  "model": "openai/gpt-4o-mini",\n  "temperature": 0.2,\n  "messages": [\n    {\n      "role": "system",\n      "content": "Отвечай коротко, профессионально и только по базе знаний компании. Если факта нет, предложи оставить заявку."\n    },\n    {\n      "role": "user",\n      "content": "{user_question}"\n    }\n  ]\n}',
      timeout: 20,
      response_map: '{\n  "ai_answer": "choices.0.message.content"\n}',
    } },
  },
  {
    id: 'n_ai_check', type: 'block', position: { x: 40, y: 800 },
    data: { group: 'block', type: 'condition', params: { expression: 'ai_answer' } },
  },
  {
    id: 'n_ai_answer', type: 'block', position: { x: -150, y: 980 },
    data: { group: 'block', type: 'show_buttons', params: {
      text: '{ai_answer}',
      buttons: [
        { label: 'Ещё вопрос', action: 'next', target: 'n_ask_prompt' },
        { label: 'Оставить заявку', action: 'next', target: 'req_start' },
        { label: 'В меню', action: 'next', target: 'n_menu' },
      ],
    } },
  },
  {
    id: 'n_ai_error', type: 'block', position: { x: 240, y: 980 },
    data: { group: 'block', type: 'show_buttons', params: {
      text: 'Не получилось получить ответ прямо сейчас. Могу передать вопрос разработчику или оформить заявку.',
      buttons: [
        { label: 'Передать разработчику', action: 'next', target: 'dev_start' },
        { label: 'Оставить заявку', action: 'next', target: 'req_start' },
        { label: 'В меню', action: 'next', target: 'n_menu' },
      ],
    } },
  },

  {
    id: 'n_open_app', type: 'block', position: { x: 420, y: 460 },
    data: { group: 'block', type: 'open_mini_app', params: {
      text: 'Откройте mini app внутри мессенджера.',
      button_text: 'Открыть',
      save_as: 'cart',
    } },
  },
  {
    id: 'n_after_app', type: 'block', position: { x: 420, y: 640 },
    data: { group: 'block', type: 'show_buttons', params: {
      text: 'Результат mini app сохранён: {cart}',
      buttons: [{ label: 'В меню', action: 'next', target: 'n_menu' }],
    } },
  },

  {
    id: 'req_start', type: 'block', position: { x: 730, y: 460 },
    data: { group: 'block', type: 'send_message', params: {
      text: 'Оформим заявку. Задам несколько коротких вопросов.',
      attachment: '',
    } },
  },
  {
    id: 'req_ask_name', type: 'block', position: { x: 730, y: 620 },
    data: { group: 'block', type: 'ask', params: { prompt: 'Как к вам обращаться?', save_as: 'req_name', validation: '' } },
  },
  {
    id: 'req_ask_contact', type: 'block', position: { x: 730, y: 780 },
    data: { group: 'block', type: 'ask', params: { prompt: 'Оставьте контакт для связи.', save_as: 'req_contact', validation: '' } },
  },
  {
    id: 'req_ask_task', type: 'block', position: { x: 730, y: 940 },
    data: { group: 'block', type: 'ask', params: { prompt: 'Опишите задачу: что нужно сделать?', save_as: 'req_task', validation: '' } },
  },
  {
    id: 'req_summary', type: 'block', position: { x: 730, y: 1100 },
    data: { group: 'block', type: 'show_buttons', params: {
      text: 'Проверьте заявку:\n\nИмя: {req_name}\nКонтакт: {req_contact}\nЗадача: {req_task}\n\nВсё верно?',
      buttons: [
        { label: 'Подтвердить', action: 'next', target: 'req_done' },
        { label: 'Заполнить заново', action: 'next', target: 'req_start' },
        { label: 'Отменить', action: 'next', target: 'n_menu' },
      ],
    } },
  },
  {
    id: 'req_done', type: 'block', position: { x: 730, y: 1260 },
    data: { group: 'block', type: 'send_message', params: {
      text: 'Готово, {req_name}! Заявка принята. Специалист свяжется с вами: {req_contact}.',
      attachment: '',
    } },
  },

  {
    id: 'dev_start', type: 'block', position: { x: 1040, y: 460 },
    data: { group: 'block', type: 'send_message', params: {
      text: 'Передам вопрос разработчику. Опишите его в двух шагах.',
      attachment: '',
    } },
  },
  {
    id: 'dev_ask_message', type: 'block', position: { x: 1040, y: 620 },
    data: { group: 'block', type: 'ask', params: { prompt: 'Что передать разработчику?', save_as: 'dev_message', validation: '' } },
  },
  {
    id: 'dev_ask_contact', type: 'block', position: { x: 1040, y: 780 },
    data: { group: 'block', type: 'ask', params: { prompt: 'Как с вами связаться?', save_as: 'dev_contact', validation: '' } },
  },
  {
    id: 'dev_done', type: 'block', position: { x: 1040, y: 940 },
    data: { group: 'block', type: 'show_buttons', params: {
      text: 'Передал! Разработчик свяжется с вами: {dev_contact}.',
      buttons: [{ label: 'В меню', action: 'next', target: 'n_menu' }],
    } },
  },
]

export const initialEdges = [
  { id: 'e-t-start-greet', source: 't_start', target: 'n_greet', ...arrow },
  { id: 'e-t-menu-menu', source: 't_menu', target: 'n_menu', ...arrow },
  { id: 'e-t-mini-after', source: 't_mini_result', target: 'n_after_app', ...arrow },
  { id: 'e-greet-menu', source: 'n_greet', target: 'n_menu', sourceHandle: 'next', ...arrow },

  { id: 'e-ask-ai', source: 'n_ask_prompt', target: 'n_ai', sourceHandle: 'next', ...arrow },
  { id: 'e-ai-check', source: 'n_ai', target: 'n_ai_check', sourceHandle: 'next', ...arrow },
  { id: 'e-ai-error', source: 'n_ai', target: 'n_ai_error', sourceHandle: 'error', label: 'ошибка', ...error },
  { id: 'e-check-answer', source: 'n_ai_check', target: 'n_ai_answer', sourceHandle: 'true', label: 'да', ...yes },
  { id: 'e-check-error', source: 'n_ai_check', target: 'n_ai_error', sourceHandle: 'false', label: 'нет', ...no },

  { id: 'e-mini-after', source: 'n_open_app', target: 'n_after_app', sourceHandle: 'next', ...arrow },

  { id: 'e-req-start-name', source: 'req_start', target: 'req_ask_name', sourceHandle: 'next', ...arrow },
  { id: 'e-req-name-contact', source: 'req_ask_name', target: 'req_ask_contact', sourceHandle: 'next', ...arrow },
  { id: 'e-req-contact-task', source: 'req_ask_contact', target: 'req_ask_task', sourceHandle: 'next', ...arrow },
  { id: 'e-req-task-summary', source: 'req_ask_task', target: 'req_summary', sourceHandle: 'next', ...arrow },

  { id: 'e-dev-start-message', source: 'dev_start', target: 'dev_ask_message', sourceHandle: 'next', ...arrow },
  { id: 'e-dev-message-contact', source: 'dev_ask_message', target: 'dev_ask_contact', sourceHandle: 'next', ...arrow },
  { id: 'e-dev-contact-done', source: 'dev_ask_contact', target: 'dev_done', sourceHandle: 'next', ...arrow },
]
