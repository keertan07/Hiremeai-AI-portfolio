# Streaming change report

| Before | After | Meaning |
| --- | --- | --- |
| Browser waited for a full JSON answer | Frontend sends `stream: true` and reads server-sent events over fetch | Answer text appears incrementally as Groq generates it. |
| One complete Groq result | Groq `stream=True`, forwarded through FastAPI StreamingResponse | This is provider streaming, not a typing animation applied after generation. |
| Only a JSON API response | Same `/chat` supports JSON by default or SSE when requested | Existing callers and the configured API URL remain compatible. |
| Separate full-answer prompt | Both modes reuse `build_candidate_messages` | Resume facts and conversation context stay consistent. |
| Full answer appended once | One identified AI message is updated as chunks arrive | Tokens stay in the correct chat, with no duplicate answer bubbles. |
| Waiting indicator until completion | Waiting dots until the first chunk, then live text and a Stop button | Visitors can see progress and stop the browser request. |
| Basic request failure handling | Handles HTTP errors, stream errors, malformed data, and missing completion | Failed or incomplete responses are not silently treated as successes. |
| Only completed generation supported | Explicit upstream stream cleanup on error/disconnect | Stop closes the browser connection; the server closes its provider stream when the current blocking read returns. |
| Default whitespace rendering | Preserved answer newlines | Paragraphs and stopped-response labels remain readable. |

## Protocol

Request: `POST /chat` with `conversation_id`, `question`, and optional `stream: true`.
Streaming content type: `text/event-stream`. Each frame is a `data:` line containing
JSON, followed by a blank line:

```text
data: {"type":"delta","text":"Hello"}

data: {"type":"done","conversation_id":"...","answer":"Hello"}

```

`delta` appends text; `done` confirms a complete, validated answer. Failures after
streaming starts use `{"type":"error","detail":"..."}` because HTTP headers
have already been sent. The frontend buffers frames and UTF-8 characters split
across network chunks. It replaces partial answers on errors and labels manually
stopped answers. History is committed only after normal provider completion, before
the `done` frame; stopping after that point cannot undo the completed server turn.

## Checks and deployment

- 14 backend tests cover JSON compatibility, streaming, completion, truncation,
  timeouts, cleanup, and existing cache/validation behavior.
- 5 frontend parser tests cover fragmented UTF-8/frames, errors, disconnects,
  cancellation, and invalid responses.
- Frontend lint and production build pass.
- Tests mock Groq; live Groq and hosted proxy buffering have not been verified.
- Deploy/restart both backend and frontend. The existing VITE_API_URL still points
  to `/chat`. Disable response buffering on any additional proxy in front of the API;
  the backend already sends no-cache/no-transform and X-Accel-Buffering headers.
- The first request after a resume change still waits for resume parsing before
  answer tokens arrive. Stop does not reverse tokens already generated, and a
  blocking provider read can delay server cleanup until its network timeout.

Implementation references: [Groq streaming](https://console.groq.com/docs/text-chat)
and [FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse).
