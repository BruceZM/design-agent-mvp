from langchain_openai import ChatOpenAI

from .config import Settings


class GLMChatOpenAI(ChatOpenAI):
    """Preserve GLM reasoning between the MVP's non-streaming tool calls."""

    def _create_chat_result(self, response, generation_info=None):
        result = super()._create_chat_result(response, generation_info)
        data = response if isinstance(response, dict) else response.model_dump()
        for generation, choice in zip(result.generations, data["choices"], strict=True):
            reasoning = choice["message"].get("reasoning_content")
            if reasoning is not None:
                generation.message.additional_kwargs["reasoning_content"] = reasoning
        return result

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        messages = self._convert_input(input_).to_messages()
        for message, serialized in zip(messages, payload["messages"], strict=True):
            reasoning = message.additional_kwargs.get("reasoning_content")
            if serialized["role"] == "assistant" and reasoning is not None:
                serialized["reasoning_content"] = reasoning
        return payload


def create_model(settings: Settings, *, vision=False) -> GLMChatOpenAI:
    name = settings.vision_model if vision else settings.model
    parameters = {
        "temperature": 0.2,
        "extra_body": {"thinking": {"type": "disabled"}},
    }
    if name.lower().startswith("glm-5.3"):
        # GLM-5.3-Flash cannot disable thinking. Low effort bounds MVP latency;
        # retaining reasoning supports consecutive tool calls and prompt caching.
        parameters = {
            "temperature": 1.0,
            "top_p": 0.95,
            "reasoning_effort": "low",
            "extra_body": {"thinking": {"type": "enabled", "clear_thinking": False}},
        }
    return GLMChatOpenAI(
        model=name,
        api_key=settings.api_key,
        base_url=settings.vision_base_url if vision else settings.base_url,
        timeout=90,
        max_retries=0,
        max_tokens=2200 if vision else 6500,
        **parameters,
    )
