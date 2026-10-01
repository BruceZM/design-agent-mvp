# 后端配置入口：其他模块依赖 Settings，不各自读取环境变量。
# 阅读顺序：配置 → main.py 接收上传 → worker.py → workflow.py。
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# 从本文件定位 design-agent/，不依赖执行命令时的当前目录。
# dotenv 默认不覆盖进程中已有变量；部署时可用环境变量覆盖本地 .env。
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


@dataclass
class Settings:
    # dataclass 自动生成初始化方法，测试可传入临时目录、假密钥和较小预算。
    # default_factory 在“创建配置对象”时读取变量，避免导入时固定所有值。
    root: Path = ROOT
    # MVP 的开发目标固定为同级 CRM；网页不能指定任意本地路径或仓库。
    target: Path = field(default_factory=lambda: ROOT.parent / "customer-manager")
    runtime: Path = field(default_factory=lambda: ROOT / "runtime")
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    # ChatOpenAI 在这里仅作为协议适配器；实际调用的是这些地址上的 GLM。
    base_url: str = field(
        default_factory=lambda: os.getenv(
            "LLM_BASE_URL", "https://open.bigmodel.cn/api/coding/paas/v4"
        )
    )
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "glm-5.3-flash"))
    # 识图和编码分别配置模型/地址，当前默认相同，也共用一个后端密钥。
    vision_mode: str = field(
        default_factory=lambda: os.getenv("VISION_MODE", "remote")
    )
    vision_model: str = field(
        default_factory=lambda: os.getenv("VISION_MODEL", "glm-5.3-flash")
    )
    vision_base_url: str = field(
        default_factory=lambda: os.getenv(
            "VISION_BASE_URL", "https://open.bigmodel.cn/api/coding/paas/v4"
        )
    )
    max_model_calls: int = field(
        default_factory=lambda: min(20, max(1, int(os.getenv("MAX_MODEL_CALLS", "16"))))
    )
    # 修复次数限制为 0～2，默认 1；首次开发后的检查不算一次“修复”。
    max_repairs: int = field(
        default_factory=lambda: min(2, max(0, int(os.getenv("MAX_REPAIRS", "1"))))
    )
    task_timeout: int = field(
        default_factory=lambda: int(os.getenv("TASK_TIMEOUT_SECONDS", "900"))
    )

    def redact(self, value: str) -> str:
        # 仅替换当前配置的 API key，适用于事件和文本产物。
        # 这是精确字符串脱敏，并非能识别任意秘密的扫描器。
        return value.replace(self.api_key, "[REDACTED]") if self.api_key else value
