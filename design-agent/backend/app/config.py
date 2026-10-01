import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


@dataclass
class Settings:
    root: Path = ROOT
    target: Path = field(default_factory=lambda: ROOT.parent / "customer-manager")
    runtime: Path = field(default_factory=lambda: ROOT / "runtime")
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    base_url: str = field(
        default_factory=lambda: os.getenv(
            "LLM_BASE_URL", "https://open.bigmodel.cn/api/coding/paas/v4"
        )
    )
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "glm-5.3-flash"))
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
    max_repairs: int = field(
        default_factory=lambda: min(2, max(0, int(os.getenv("MAX_REPAIRS", "1"))))
    )
    task_timeout: int = field(
        default_factory=lambda: int(os.getenv("TASK_TIMEOUT_SECONDS", "900"))
    )

    def redact(self, value: str) -> str:
        return value.replace(self.api_key, "[REDACTED]") if self.api_key else value
