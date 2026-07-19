import assert from 'node:assert/strict'
import test from 'node:test'

import { ConstructorApiError, createBot, getBot, getFlowDraft, publishBot } from './adminApi.js'

function withFetch(stub, run) {
  const originalFetch = globalThis.fetch
  globalThis.fetch = stub
  return Promise.resolve(run()).finally(() => {
    globalThis.fetch = originalFetch
  })
}

test('formats FastAPI validation details into readable field errors', async () => {
  await withFetch(async () => ({
    ok: false,
    status: 422,
    statusText: 'Unprocessable Content',
    text: async () => JSON.stringify({
      detail: [
        { loc: ['body', 'name'], msg: 'Field required' },
        { loc: ['body', 'token'], msg: 'Field required' },
      ],
    }),
  }), async () => {
    await assert.rejects(
      createBot('', {}),
      (error) => error instanceof ConstructorApiError
        && error.status === 422
        && error.message === 'Проверьте данные: name: обязательное поле; token: обязательное поле',
    )
  })
})

test('turns a network failure into an actionable message', async () => {
  await withFetch(async () => {
    throw new TypeError('Failed to fetch')
  }, async () => {
    await assert.rejects(
      createBot('', { name: 'Тест', platform: 'telegram', token: 'secret' }),
      /Не удалось связаться с API/,
    )
  })
})

test('keeps not-found details generic instead of exposing an identifier from the server', async () => {
  await withFetch(async () => ({
    ok: false,
    status: 404,
    statusText: 'Not Found',
    text: async () => JSON.stringify({ detail: 'bot private-id-123 was not found' }),
  }), async () => {
    await assert.rejects(
      getBot('', 'private-id-123'),
      (error) => error instanceof ConstructorApiError
        && error.status === 404
        && error.message === 'Запрошенный бот не найден. Возможно, он был удалён в другом сеансе.',
    )
  })
})

test('returns the flow draft payload for the editor (200)', async () => {
  const draft = {
    flow_id: 'flow-1',
    name: 'Заявки',
    definition: { doc_schema_version: 1, triggers: [], nodes: [], transitions: [] },
    row_version: 4,
  }
  await withFetch(async () => ({
    ok: true,
    status: 200,
    statusText: 'OK',
    text: async () => JSON.stringify(draft),
  }), async () => {
    assert.deepEqual(await getFlowDraft('', 'bot-1'), draft)
  })
})

test('returns null when the bot has no draft yet (204 keeps the editor on a clean slate)', async () => {
  await withFetch(async () => ({
    ok: true,
    status: 204,
    statusText: 'No Content',
    text: async () => '',
  }), async () => {
    assert.equal(await getFlowDraft('', 'bot-1'), null)
  })
})

test('flow draft for a missing bot surfaces the generic not-found message', async () => {
  await withFetch(async () => ({
    ok: false,
    status: 404,
    statusText: 'Not Found',
    text: async () => JSON.stringify({ detail: 'bot secret-id was not found' }),
  }), async () => {
    await assert.rejects(
      getFlowDraft('', 'secret-id'),
      (error) => error instanceof ConstructorApiError
        && error.status === 404
        && error.message === 'Запрошенный бот не найден. Возможно, он был удалён в другом сеансе.',
    )
  })
})

test('turns an unexpected server response into a safe message', async () => {
  await withFetch(async () => ({
    ok: false,
    status: 500,
    statusText: 'Internal Server Error',
    text: async () => JSON.stringify({ detail: 'traceback with secret value' }),
  }), async () => {
    await assert.rejects(
      publishBot('', 'bot-1'),
      (error) => error instanceof ConstructorApiError
        && error.status === 500
        && error.message === 'Ошибка сервера. Изменения не сохранены — повторите попытку позже.',
    )
  })
})
