# GLM 的 LangChain 协议适配集中放在这里，视觉和编码复用同一个模型工厂。
# 当前使用非流式 invoke/ainvoke；此适配不声称覆盖流式响应路径。
from langchain_openai import ChatOpenAI

from .config import Settings


class GLMChatOpenAI(ChatOpenAI):
    """Preserve GLM reasoning between the MVP's non-streaming tool calls."""

    def _create_chat_result(self, response, generation_info=None):
        # 先复用父类解析正文、tool_calls、usage，再保留 GLM 特有的推理字段。
        # 若只保留正文，下一轮工具结果回传时会丢失模型要求的思考上下文。
        result = super()._create_chat_result(response, generation_info)
        data = response if isinstance(response, dict) else response.model_dump()
        # zip(strict=True) 要求两侧选择项数量一致，协议异常时不静默错配。
        for generation, choice in zip(result.generations, data["choices"], strict=True):
            reasoning = choice["message"].get("reasoning_content")
            if reasoning is not None:
                generation.message.additional_kwargs["reasoning_content"] = reasoning
        return result

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        # 在发请求前将保存在 AIMessage 上的 reasoning_content 放回 assistant 消息。
        # additional_kwargs 是消息的扩展字段容器，并不是发给工具的参数。
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        messages = self._convert_input(input_).to_messages()
        for message, serialized in zip(messages, payload["messages"], strict=True):
            reasoning = message.additional_kwargs.get("reasoning_content")
            if serialized["role"] == "assistant" and reasoning is not None:
                serialized["reasoning_content"] = reasoning
        return payload


def create_model(settings: Settings, *, vision=False) -> GLMChatOpenAI:
    # vision 为仅限关键字参数，调用处写 vision=True 可直观看出用途。
    # 统一工厂避免视觉/计划/编码各自复制不同的协议和重试配置。
    name = settings.vision_model if vision else settings.model
    parameters = {
        "temperature": 0.2,
        "extra_body": {"thinking": {"type": "disabled"}},
    }
    if name.lower().startswith("glm-5.3"):
        # 此项目的 GLM-5.3 配置启用思考，用 low effort 控制延迟。
        # clear_thinking=False 配合上述消息适配保留连续工具调用的上下文。
        parameters = {
            "temperature": 1.0,
            "top_p": 0.95,
            "reasoning_effort": "low",
            "extra_body": {"thinking": {"type": "enabled", "clear_thinking": False}},
        }
    return GLMChatOpenAI(
        # max_tokens 是单次响应上限；任务总调用次数由 agent.Budget 单独控制。
        # max_retries=0 关闭 SDK 重试，模型请求失败由外层工作流显式记录。
        model=name,
        api_key=settings.api_key,
        base_url=settings.vision_base_url if vision else settings.base_url,
        timeout=90,
        max_retries=0,
        max_tokens=2200 if vision else 6500,
        **parameters,
    )
