import { MarkerType } from '@xyflow/react'
import { buttonHandleId } from './handles.js'

const arrow = { markerEnd: { type: MarkerType.ArrowClosed } }
const buttonEdge = (source, index, target, label) => ({
  id: `e-${source}-button-${index}`,
  source,
  sourceHandle: buttonHandleId(index),
  target,
  label,
  style: { stroke: '#4F46E5' },
  labelStyle: { fill: '#4338CA', fontWeight: 700 },
  markerEnd: { type: MarkerType.ArrowClosed, color: '#4F46E5' },
})

export const initialNodes = [
  {
    id: 't_start', type: 'trigger', position: { x: 420, y: 0 },
    data: { group: 'trigger', type: 'start', label: 'Команда /start', icon: '⚑', config: {} },
  },
  {
    id: 'n_welcome', type: 'block', position: { x: 420, y: 150 },
    data: { group: 'block', type: 'send_message', params: {
      text: 'Здравствуйте! Я помогу сориентироваться и принять заявку.',
    } },
  },
  {
    id: 'n_menu', type: 'block', position: { x: 420, y: 310 },
    data: { group: 'block', type: 'show_buttons', params: {
      text: 'Что вы хотите сделать?',
      buttons: [
        { label: 'Оставить заявку', action: 'next', target: 'n_ask_name' },
        { label: 'Как это работает', action: 'next', target: 'n_help' },
      ],
    } },
  },
  {
    id: 'n_ask_name', type: 'block', position: { x: 220, y: 510 },
    data: { group: 'block', type: 'ask', params: {
      prompt: 'Как к вам обращаться?',
      save_as: 'name',
    } },
  },
  {
    id: 'n_done', type: 'block', position: { x: 220, y: 670 },
    data: { group: 'block', type: 'send_message', params: {
      text: 'Спасибо, {name}! Мы получили заявку и скоро свяжемся с вами.',
    } },
  },
  {
    id: 'n_help', type: 'block', position: { x: 650, y: 510 },
    data: { group: 'block', type: 'show_buttons', params: {
      text: 'Сценарий — это граф: входы, действия и переходы. Добавляйте свои блоки из палитры.',
      buttons: [{ label: 'Вернуться в меню', action: 'next', target: 'n_menu' }],
    } },
  },
]

export const initialEdges = [
  { id: 'e-t-start-welcome', source: 't_start', target: 'n_welcome', ...arrow },
  { id: 'e-welcome-menu', source: 'n_welcome', target: 'n_menu', sourceHandle: 'next', ...arrow },
  buttonEdge('n_menu', 0, 'n_ask_name', 'Оставить заявку'),
  buttonEdge('n_menu', 1, 'n_help', 'Как это работает'),
  { id: 'e-ask-done', source: 'n_ask_name', target: 'n_done', sourceHandle: 'next', ...arrow },
  buttonEdge('n_help', 0, 'n_menu', 'Вернуться в меню'),
]
