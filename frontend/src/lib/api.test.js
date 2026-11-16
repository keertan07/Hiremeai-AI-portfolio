import assert from 'node:assert/strict';
import test from 'node:test';
import { getApiUrl } from './api.js';

test('development uses the local backend even when .env contains the public URL', () => {
  assert.equal(getApiUrl(true, 'https://example.test/chat'), 'http://127.0.0.1:8000/chat');
});

test('a deployed site uses Render when its API setting is missing', () => {
  assert.equal(getApiUrl(false, undefined), 'https://hiremeai-ai-portfolio.onrender.com/chat');
  assert.equal(getApiUrl(false, ''), 'https://hiremeai-ai-portfolio.onrender.com/chat');
});

test('a deployed site honors its configured backend', () => {
  assert.equal(getApiUrl(false, 'https://example.test/chat'), 'https://example.test/chat');
});

test('a server URL without /chat still sends questions to /chat', () => {
  for (const setting of ['https://example.test', 'https://example.test/',
    'https://example.test/chat/', '  https://example.test/  ']) {
    assert.equal(getApiUrl(false, setting), 'https://example.test/chat');
  }
});

test('a whitespace-only setting uses the public backend', () => {
  assert.equal(getApiUrl(false, '   '), 'https://hiremeai-ai-portfolio.onrender.com/chat');
});
