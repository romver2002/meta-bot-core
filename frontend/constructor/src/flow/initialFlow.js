import { MarkerType } from '@xyflow/react'

// Пример собранного сценария «кофейни»: /start → приветствие → кнопки →
// вопрос имени → развилка → (да) открыть mini app / (нет) отправить заявку по API.

export const initialNodes = [
  {
    id: 't1', type: 'trigger', position: { x: 300, y: 0 },
    data: { group: 'trigger', type: 'start', label: 'Команда /start', icon: '⚑' },
  },
  {
    id: 'b1', type: 'block', position: { x: 285, y: 120 },
    data: { group: 'block', type: 'send_message', params: {
      text: 'Привет, {name}! 👋 Добро пожаловать в кофейню.', attachment: '' } },
  },
  {
    id: 'b2', type: 'block', position: { x: 285, y: 250 },
    data: { group: 'block', type: 'show_buttons', params: {
      text: 'Что хотите сделать?',
      buttons: [
        { label: 'Записаться', action: 'callback' },
        { label: 'Открыть каталог', action: 'open_mini_app' },
      ] } },
  },
  {
    id: 'b3', type: 'block', position: { x: 285, y: 400 },
    data: { group: 'block', type: 'ask', params: {
      prompt: 'Как вас зовут?', save_as: 'name', validation: 'none' } },
  },
  {
    id: 'b4', type: 'block', position: { x: 300, y: 545 },
    data: { group: 'block', type: 'condition', params: { expression: 'name != ""' } },
  },
  {
    id: 'b5', type: 'block', position: { x: 90, y: 700 },
    data: { group: 'block', type: 'open_mini_app', params: {
      mini_app: 'catalog', button_text: 'Открыть каталог' } },
  },
  {
    id: 'b6', type: 'block', position: { x: 500, y: 700 },
    data: { group: 'block', type: 'http_request', params: {
      method: 'POST', url: 'https://api.example.com/lead',
      headers: '{"Content-Type": "application/json"}', response_map: 'lead_id = data.id' } },
  },
]

const arrow = { markerEnd: { type: MarkerType.ArrowClosed } }

export const initialEdges = [
  { id: 'e-t1-b1', source: 't1', target: 'b1', ...arrow },
  { id: 'e-b1-b2', source: 'b1', target: 'b2', ...arrow },
  { id: 'e-b2-b3', source: 'b2', target: 'b3', label: 'callback', ...arrow },
  { id: 'e-b3-b4', source: 'b3', target: 'b4', ...arrow },
  { id: 'e-b4-b5', source: 'b4', target: 'b5', sourceHandle: 'true', label: 'да',
    style: { stroke: '#16A34A' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#16A34A' } },
  { id: 'e-b4-b6', source: 'b4', target: 'b6', sourceHandle: 'false', label: 'нет',
    style: { stroke: '#64748B' }, markerEnd: { type: MarkerType.ArrowClosed, color: '#64748B' } },
]
