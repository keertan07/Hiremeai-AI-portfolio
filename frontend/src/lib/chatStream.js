// Read answer events from fetch. A network piece can end halfway through an event
// or a character, so keep unfinished data until the next piece arrives.
export async function readChatStream(response, onEvent) {
  if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream')) {
    throw new Error('The server did not return an answer stream.');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      // Accept Windows or Unix line endings, even when split across reads.
      buffer = buffer.replace(/\r\n/g, '\n');
      let boundary;
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = frame.split('\n').filter(line => line.startsWith('data:'))
          .map(line => line.slice(5).trimStart()).join('\n');
        if (!data) continue; // Skip empty events and connection keep-alive notes.
        let event;
        try {
          event = JSON.parse(data);
        } catch {
          throw new Error('The server sent an unreadable answer. Please try again.');
        }
        if (!event || !['delta', 'done', 'error'].includes(event.type)) {
          throw new Error('The server sent an unreadable answer. Please try again.');
        }
        if (event.type === 'error') throw new Error(event.detail || 'The answer was interrupted.');
        if (event.type === 'delta' && typeof event.text !== 'string') throw new Error('Invalid answer stream.');
        if (event.type === 'done' && (typeof event.answer !== 'string' || !event.answer.trim())) {
          throw new Error('The server returned an empty answer.');
        }
        onEvent(event);
        if (event.type === 'done') return;
      }
      if (done) throw new Error('The connection ended before the answer finished. Please try again.');
    }
  } finally {
    // Also closes the connection after an error or an explicit Stop request.
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
