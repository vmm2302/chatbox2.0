import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import {
  setAuthToken,
  getAuthToken,
  setUnauthorizedHandler,
  notifyUnauthorized,
  getAuthHeaders,
  loginUser,
  logoutUser,
  streamChatMessage,
} from '../src/services/api.js';
import { getLevelConfig, CEFR_LEVELS } from '../src/utils/cefr.js';
import { getInitialTheme, applyTheme } from '../src/utils/theme.js';

describe('API Auth Token & Session Lifecycle', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    setAuthToken(null);
    setUnauthorizedHandler(null);
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    setAuthToken(null);
    setUnauthorizedHandler(null);
  });

  it('stores token in memory and attaches Bearer header', () => {
    assert.equal(getAuthToken(), null);
    assert.deepEqual(getAuthHeaders({ 'X-Custom': '1' }), { 'X-Custom': '1' });

    setAuthToken('jwt.sample.token');
    assert.equal(getAuthToken(), 'jwt.sample.token');
    assert.deepEqual(getAuthHeaders({ 'Content-Type': 'application/json' }), {
      'Content-Type': 'application/json',
      Authorization: 'Bearer jwt.sample.token',
    });
  });

  it('clears token and triggers unauthorized handler once on 401', async () => {
    let calls = 0;
    setAuthToken('expired.token');
    setUnauthorizedHandler(() => {
      calls += 1;
    });

    notifyUnauthorized();
    notifyUnauthorized();

    assert.equal(getAuthToken(), null);
    assert.equal(calls, 1);
  });

  it('sets auth token on loginUser and revokes on logoutUser', async () => {
    const requests = [];
    globalThis.fetch = async (url, init = {}) => {
      requests.push({ url, init });
      if (url === '/api/auth/login') {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            access_token: 'issued.bearer.token',
            user: { id: 10, username: 'learner1', role: 'user' },
          }),
        };
      }
      return { ok: true, status: 200, json: async () => ({ status: 'success' }) };
    };

    const loginRes = await loginUser('learner1', 'Secret123!');
    assert.equal(loginRes.user.username, 'learner1');
    assert.equal(getAuthToken(), 'issued.bearer.token');

    await logoutUser();
    assert.equal(getAuthToken(), null);
    assert.equal(requests[1].url, '/api/auth/logout');
    assert.equal(requests[1].init.headers.Authorization, 'Bearer issued.bearer.token');
  });

  it('parses SSE status, token, and final events cleanly', async () => {
    setAuthToken('sse.token');
    const encoder = new TextEncoder();
    const ssePayload = [
      'data: {"type":"status","text":"Đang tìm..."}\n\n',
      'data: {"type":"token","token":"Từ bạn tìm kiếm: apple\\n\\n"}\n\n',
      'data: {"type":"final","reply":"Từ bạn tìm kiếm: apple","conversation_id":"c1","structured_card":{"word":"apple","level":"A1"},"meta":{"mode":"DIRECT_MATCH"}}\n\n',
      'data: [DONE]\n\n',
    ].join('');

    globalThis.fetch = async () => ({
      ok: true,
      status: 200,
      body: new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode(ssePayload));
          controller.close();
        },
      }),
    });

    const statuses = [];
    const tokens = [];
    let finalEvent = null;
    let streamError = null;

    await streamChatMessage({
      query: 'apple',
      userId: 10,
      onStatus: (s) => statuses.push(s),
      onToken: (t) => tokens.push(t),
      onFinal: (f) => {
        finalEvent = f;
      },
      onError: (err) => {
        streamError = err;
      },
    });

    assert.equal(streamError, null);
    assert.deepEqual(statuses, ['Đang tìm...']);
    assert.equal(tokens.length, 1);
    assert.equal(finalEvent.structured_card.word, 'apple');
    assert.equal(finalEvent.conversation_id, 'c1');
  });
});

describe('CEFR Dynamic Styling & Theme Utils', () => {
  it('returns predefined configs for A1-C2 and dynamic config for custom levels', () => {
    assert.equal(getLevelConfig('a1').id, CEFR_LEVELS.A1.id);
    assert.equal(getLevelConfig('B2').color, 'purple');

    const custom = getLevelConfig('TOEIC600');
    assert.equal(custom.id, 'TOEIC600');
    assert.ok(custom.badge.includes('TOEIC600'));
    assert.ok(custom.gradient.length > 0);
  });

  it('handles theme helpers safely without DOM globals', () => {
    assert.equal(getInitialTheme(), 'system');
    applyTheme('dark');
  });
});
