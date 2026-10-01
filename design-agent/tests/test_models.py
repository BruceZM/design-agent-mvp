import asyncio
import base64
import json

import httpx
import pytest
from langchain_core.messages import ToolMessage

from app import models, vision
from app.config import Settings


def test_glm_thinking_survives_a_tool_round_trip(monkeypatch):
    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body["model"] == "glm-5.3-flash"
        assert body["thinking"] == {"type": "enabled", "clear_thinking": False}
        assert body["reasoning_effort"] == "low"
        if len(requests) == 1:
            message = {
                "role": "assistant",
                "content": "",
                "reasoning_content": "Need to inspect the existing component first.",
                "tool_calls": [{
                    "id": "read-1", "type": "function",
                    "function": {"name": "read_file", "arguments": '{"path":"src/App.tsx"}'},
                }],
            }
            reason = "tool_calls"
        else:
            previous = body["messages"][1]
            assert previous["reasoning_content"] == "Need to inspect the existing component first."
            assert previous["tool_calls"][0]["id"] == "read-1"
            assert body["messages"][2]["role"] == "tool"
            assert body["messages"][2]["tool_call_id"] == "read-1"
            message = {"role": "assistant", "content": "Component read."}
            reason = "stop"
        return httpx.Response(200, json={
            "id": "completion-test", "object": "chat.completion", "created": 0,
            "model": "glm-5.3-flash",
            "choices": [{"index": 0, "message": message, "finish_reason": reason}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        })

    actual_client = models.GLMChatOpenAI
    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        monkeypatch.setattr(models, "GLMChatOpenAI", lambda **kwargs: actual_client(
            http_client=transport, **kwargs,
        ))
        model = models.create_model(Settings(
            api_key="fake-model-test-key", model="glm-5.3-flash",
            base_url="https://model-test.invalid/v4",
        ))
        user = {"role": "user", "content": "Read the component."}
        first = model.invoke([user])
        reply = model.invoke([user, first, ToolMessage(
            content="export default function App() {}", tool_call_id="read-1",
        )])
    assert reply.content == "Component read."
    assert len(requests) == 2


def test_multimodal_parser_sends_original_image_and_marks_provenance(tmp_path, monkeypatch):
    image = tmp_path / "design.png"
    image.write_bytes(b"original-image-fixture")
    settings = Settings(api_key="fake-vision-test-key", vision_mode="remote", vision_model="glm-5.3-flash")

    class VisualModel:
        async def ainvoke(self, messages):
            blocks = messages[0]["content"]
            assert blocks[0]["type"] == "text" and blocks[0]["text"]
            assert blocks[1]["type"] == "image_url"
            assert base64.b64decode(blocks[1]["image_url"]["url"].split(",", 1)[1]) == image.read_bytes()
            return type("Reply", (), {"content": "## 可见状态\n搜索结果 6；颜色为估计值。"})()

    def create_model(config, *, vision=False):
        assert config is settings and vision
        return VisualModel()

    monkeypatch.setattr(vision, "create_model", create_model)
    spec = asyncio.run(vision.describe_image(settings, image))
    assert "remote（视觉大模型）" in spec and "glm-5.3-flash" in spec
    assert "搜索结果 6" in spec


def test_multimodal_failure_stops_without_ocr_fallback(tmp_path, monkeypatch):
    image = tmp_path / "design.png"
    image.write_bytes(b"fixture")
    settings = Settings(api_key="fake-vision-test-key", vision_mode="remote")

    class DeniedModel:
        async def ainvoke(self, messages):
            raise RuntimeError("model request denied")

    monkeypatch.setattr(vision, "create_model", lambda *args, **kwargs: DeniedModel())
    with pytest.raises(RuntimeError, match="model request denied"):
        asyncio.run(vision.describe_image(settings, image))
