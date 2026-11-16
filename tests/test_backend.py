import os
import json
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from groq import APITimeoutError

with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}):
    from backend import main


def completion(content, finish_reason="stop"):
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content), finish_reason=finish_reason
    )])


def stream_chunk(content=None, finish_reason=None):
    return SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(content=content), finish_reason=finish_reason
    )])


class FakeStream:
    def __init__(self, chunks):
        self.chunks = iter(chunks)
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def __iter__(self):
        return self.chunks


class BackendTests(unittest.TestCase):
    def setUp(self):
        main.limiter.reset()
        main._conversation_store.clear()
        self.client = TestClient(main.app)
        self.payload = {"conversation_id": str(uuid4()), "question": "What are your skills?"}

    def test_chat_preserves_follow_up_context(self):
        with patch.object(main, "get_cached_resume", return_value=main.Resume(name="Candidate")), \
                patch.object(main.client.chat.completions, "create", return_value=completion("Python")) as provider:
            first = self.client.post("/chat", json=self.payload)
            second = self.client.post("/chat", json={**self.payload, "question": "Explain that skill"})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["conversation_id"], self.payload["conversation_id"])
        messages = provider.call_args.kwargs["messages"]
        self.assertEqual([m["role"] for m in messages], ["system", "user", "assistant", "user"])
        self.assertEqual(provider.call_args.kwargs["max_completion_tokens"], main.CHAT_MAX_TOKENS)

    def test_invalid_or_truncated_answers_are_not_saved(self):
        responses = [SimpleNamespace(choices=[]), completion(None), completion(""),
                     completion("partial", "length"), completion("partial", "content_filter")]
        for response in responses:
            with self.subTest(response=response), \
                    patch.object(main, "get_cached_resume", return_value=main.Resume(name="Candidate")), \
                    patch.object(main.client.chat.completions, "create", return_value=response):
                result = self.client.post("/chat", json=self.payload)
            self.assertEqual(result.status_code, 502)
            self.assertEqual(main.get_conversation_history(self.payload["conversation_id"]), [])

    def test_timeout_returns_504(self):
        timeout = APITimeoutError(request=httpx.Request("POST", "https://example.test"))
        with patch.object(main, "get_cached_resume", return_value=main.Resume(name="Candidate")), \
                patch.object(main.client.chat.completions, "create", side_effect=timeout):
            result = self.client.post("/chat", json=self.payload)
        self.assertEqual(result.status_code, 504)

    def test_parser_rejects_bad_and_truncated_responses(self):
        responses = [SimpleNamespace(choices=[]), completion("invalid JSON"), completion("[]"),
                     completion('{"name":"Candidate"}', "length")]
        for response in responses:
            with self.subTest(response=response), \
                    patch.object(main.client.chat.completions, "create", return_value=response):
                with self.assertRaises(main.ResumeParsingError):
                    main.parse_resume("Sample resume")

    def test_parser_still_accepts_valid_resume(self):
        with patch.object(main.client.chat.completions, "create", return_value=completion('{"name":"Candidate"}')) as provider:
            resume = main.parse_resume("Sample resume")
        self.assertEqual(resume.name, "Candidate")
        self.assertEqual(provider.call_args.kwargs["max_completion_tokens"], main.RESUME_MAX_TOKENS)

    def test_cache_detects_changes_with_same_size_and_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resume.pdf"
            path.write_bytes(b"first")
            stat = path.stat()
            with patch.object(main, "RESUME_PATH", path), \
                    patch.object(main, "_resume_cache", {"version": None, "data": None}), \
                    patch.object(main, "extract_resume_text", side_effect=lambda p: p.read_text()), \
                    patch.object(main, "parse_resume", side_effect=[main.Resume(name="First"), main.Resume(name="Other")]) as parser:
                self.assertEqual(main.get_cached_resume().name, "First")
                self.assertEqual(main.get_cached_resume().name, "First")
                path.write_bytes(b"other")
                os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
                self.assertEqual(main.get_cached_resume().name, "Other")
                self.assertEqual(parser.call_count, 2)

    def test_health_checks_file_without_calling_provider(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(main.client.chat.completions, "create") as provider:
            path = Path(directory) / "resume.pdf"
            with patch.object(main, "RESUME_PATH", path):
                self.assertEqual(self.client.get("/health").status_code, 503)
                path.write_bytes(b"")
                self.assertEqual(self.client.get("/health").status_code, 503)
                path.write_bytes(b"sample")
                self.assertEqual(self.client.get("/health").status_code, 200)
            provider.assert_not_called()

    def test_question_and_request_size_limits(self):
        for question in ("", "  ", "x" * 501):
            result = self.client.post("/chat", json={**self.payload, "question": question})
            self.assertEqual(result.status_code, 422)
        self.assertEqual(self.client.post("/chat", content=b"x" * 4097).status_code, 413)

    def test_download_matches_the_resume_used_by_chat(self):
        response = self.client.get("/resume")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("Keertan-Resume.pdf", response.headers["content-disposition"])
        self.assertEqual(response.content, main.RESUME_PATH.read_bytes())

    def test_missing_download_returns_a_clear_error(self):
        with patch.object(main, "RESUME_PATH", Path("missing-resume-for-test.pdf")):
            response = self.client.get("/resume")
        self.assertEqual(response.status_code, 503)

    def test_our_vercel_deployments_can_call_chat(self):
        origins = [
            'https://hiremeai-ai.vercel.app',
            'https://hiremeai-ai-portfolio.vercel.app',
            'https://hiremeai-ai-portfolio-hw8ib2ujs-keertan07s-projects.vercel.app',
            'https://hiremeai-ai-portfolio-git-main-keertan07s-projects.vercel.app',
        ]
        for origin in origins:
            with self.subTest(origin=origin):
                response = self.client.options('/chat', headers={
                    'Origin': origin, 'Access-Control-Request-Method': 'POST',
                    'Access-Control-Request-Headers': 'content-type',
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['access-control-allow-origin'], origin)

    def test_other_sites_do_not_get_cors_permission(self):
        origins = [
            'https://unrelated.example',
            'https://other-project-hw8ib2ujs-keertan07s-projects.vercel.app',
            'https://hiremeai-ai-portfolio-hw8ib2ujs-other-team.vercel.app',
            'https://hiremeai-ai-portfolio-hw8ib2ujs-keertan07s-projects.vercel.app.evil.example',
        ]
        for origin in origins:
            with self.subTest(origin=origin):
                response = self.client.options('/chat', headers={
                    'Origin': origin, 'Access-Control-Request-Method': 'POST',
                })
                self.assertEqual(response.status_code, 400)
                self.assertNotIn('access-control-allow-origin', response.headers)

    def test_chat_response_is_readable_from_our_vercel_preview(self):
        origin = 'https://hiremeai-ai-portfolio-hw8ib2ujs-keertan07s-projects.vercel.app'
        stream = FakeStream([stream_chunk('Python'), stream_chunk(finish_reason='stop')])
        with patch.object(main, 'get_cached_resume', return_value=main.Resume(name='Candidate')), \
                patch.object(main.client.chat.completions, 'create', return_value=stream):
            response = self.client.post('/chat', json={**self.payload, 'stream': True},
                                        headers={'Origin': origin})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['access-control-allow-origin'], origin)
        self.assertIn('"type": "done"', response.text)

    def test_stream_yields_before_completion_and_saves_only_when_finished(self):
        payload = main.ChatRequest(**self.payload, stream=True)
        history = main.get_conversation_history(payload.conversation_id)
        stream = FakeStream([stream_chunk("Python"), stream_chunk("\n\nCafé"), stream_chunk(finish_reason="stop")])
        with patch.object(main.client.chat.completions, "create", return_value=stream) as provider:
            events = main.stream_candidate(payload, main.Resume(name="Candidate"), history)
            first = json.loads(next(events).removeprefix("data: "))
            self.assertEqual(first, {"type": "delta", "text": "Python"})
            self.assertEqual(main.get_conversation_history(payload.conversation_id), [])
            remaining = [json.loads(event.removeprefix("data: ")) for event in events]
        self.assertEqual(remaining[-1]["type"], "done")
        self.assertEqual(remaining[-1]["answer"], "Python\n\nCafé")
        self.assertEqual(main.get_conversation_history(payload.conversation_id)[-1]["content"], "Python\n\nCafé")
        self.assertTrue(provider.call_args.kwargs["stream"])
        self.assertTrue(stream.closed)

    def test_stream_endpoint_and_follow_up_history(self):
        stream = FakeStream([stream_chunk("Python"), stream_chunk(finish_reason="stop")])
        with patch.object(main, "get_cached_resume", return_value=main.Resume(name="Candidate")), \
                patch.object(main.client.chat.completions, "create", return_value=stream):
            response = self.client.post("/chat", json={**self.payload, "stream": True})
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        self.assertEqual(response.headers["x-accel-buffering"], "no")
        events = [json.loads(frame.removeprefix("data: ")) for frame in response.text.strip().split("\n\n")]
        self.assertEqual([e["type"] for e in events], ["delta", "done"])
        self.assertEqual(events[-1]["conversation_id"], self.payload["conversation_id"])
        self.assertEqual(len(main.get_conversation_history(self.payload["conversation_id"])), 2)

    def test_incomplete_streams_never_commit_history(self):
        for chunks in ([], [stream_chunk("partial")], [stream_chunk("partial", "length")],
                       [stream_chunk(finish_reason="stop")]):
            with self.subTest(chunks=chunks):
                stream = FakeStream(chunks)
                with patch.object(main, "get_cached_resume", return_value=main.Resume(name="Candidate")), \
                        patch.object(main.client.chat.completions, "create", return_value=stream):
                    response = self.client.post("/chat", json={**self.payload, "stream": True})
                self.assertIn('"type": "error"', response.text)
                self.assertNotIn('"type": "done"', response.text)
                self.assertEqual(main.get_conversation_history(self.payload["conversation_id"]), [])
                self.assertTrue(stream.closed)

    def test_timeout_during_stream_returns_error_event(self):
        def chunks():
            yield stream_chunk("partial")
            raise APITimeoutError(request=httpx.Request("POST", "https://example.test"))
        stream = FakeStream(chunks())
        with patch.object(main, "get_cached_resume", return_value=main.Resume(name="Candidate")), \
                patch.object(main.client.chat.completions, "create", return_value=stream):
            response = self.client.post("/chat", json={**self.payload, "stream": True})
        self.assertIn('"type": "delta"', response.text)
        self.assertIn('"type": "error"', response.text)
        self.assertNotIn('"type": "done"', response.text)
        self.assertEqual(main.get_conversation_history(self.payload["conversation_id"]), [])
        self.assertTrue(stream.closed)

    def test_closing_stream_releases_provider_without_saving(self):
        payload = main.ChatRequest(**self.payload, stream=True)
        main.get_conversation_history(payload.conversation_id)
        stream = FakeStream([stream_chunk("partial"), stream_chunk(finish_reason="stop")])
        with patch.object(main.client.chat.completions, "create", return_value=stream):
            events = main.stream_candidate(payload, main.Resume(name="Candidate"), [])
            next(events)
            events.close()
        self.assertTrue(stream.closed)
        self.assertEqual(main.get_conversation_history(payload.conversation_id), [])

    def test_response_iterator_closes_provider_when_cancelled(self):
        payload = main.ChatRequest(**self.payload, stream=True)
        main.get_conversation_history(payload.conversation_id)
        stream = FakeStream([stream_chunk("partial"), stream_chunk(finish_reason="stop")])

        async def disconnect():
            events = main.stream_events(payload, main.Resume(name="Candidate"), [])
            await anext(events)
            await events.aclose()

        with patch.object(main.client.chat.completions, "create", return_value=stream):
            asyncio.run(disconnect())
        self.assertTrue(stream.closed)
        self.assertEqual(main.get_conversation_history(payload.conversation_id), [])


if __name__ == "__main__":
    unittest.main()
