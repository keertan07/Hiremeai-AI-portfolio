import assert from 'node:assert/strict';
import test from 'node:test';
import { readChatStream } from './chatStream.js';

const frame = data => `data: ${JSON.stringify(data)}\n\n`;
function responseFrom(chunks) {
  return new Response(new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(chunk);
      controller.close();
    }
  }), { headers: { 'Content-Type': 'text/event-stream' } });
}

test('decodes frames and Unicode split across individual network bytes', async () => {
  const events = [
    { type: 'delta', text: 'Café 😊\n\nPython' },
    { type: 'done', answer: 'Café 😊\n\nPython', conversation_id: 'chat' }
  ];
  const bytes = new TextEncoder().encode(events.map(frame).join('').replaceAll('\n', '\r\n'));
  const received = [];
  await readChatStream(responseFrom([...bytes].map(byte => Uint8Array.of(byte))), e => received.push(e));
  assert.deepEqual(received, events);
});

test('reports server errors after partial output', async () => {
  const bytes = new TextEncoder().encode(frame({ type: 'delta', text: 'partial' }) + frame({ type: 'error', detail: 'AI timed out' }));
  const received = [];
  await assert.rejects(readChatStream(responseFrom([bytes]), e => received.push(e)), /AI timed out/);
  assert.equal(received.length, 1);
});

test('requires a completion event instead of accepting an interrupted connection', async () => {
  const bytes = new TextEncoder().encode(frame({ type: 'delta', text: 'partial' }));
  await assert.rejects(readChatStream(responseFrom([bytes]), () => {}), /before the answer finished/);
});

test('cancels the reader when event handling stops generation', async () => {
  let cancelled = false;
  const response = new Response(new ReadableStream({
    start(controller) { controller.enqueue(new TextEncoder().encode(frame({ type: 'delta', text: 'first' }))); },
    cancel() { cancelled = true; }
  }), { headers: { 'Content-Type': 'text/event-stream' } });
  await assert.rejects(readChatStream(response, () => { throw new Error('Stopped'); }), /Stopped/);
  assert.equal(cancelled, true);
});

test('rejects a regular JSON response and empty final answers', async () => {
  await assert.rejects(readChatStream(new Response('{}'), () => {}), /did not return an answer stream/);
  const bytes = new TextEncoder().encode(frame({ type: 'done', answer: '' }));
  await assert.rejects(readChatStream(responseFrom([bytes]), () => {}), /empty answer/);
});

test('shows a clear error for malformed or unknown events', async () => {
  for (const data of ['not-json', 'null', '{"type":"unknown"}']) {
    const bytes = new TextEncoder().encode(`data: ${data}\n\n`);
    await assert.rejects(readChatStream(responseFrom([bytes]), () => {}), /unreadable answer/);
  }
});
