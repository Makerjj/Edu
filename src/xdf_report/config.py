import json
from dataclasses import replace
from pathlib import Path
from typing import Callable

from .models import AppConfig


DEFAULT_TEMPLATE = Path(
    "/Users/jm/Desktop/新东方/学情反馈表/周六一档易生活102-C1-3学情反馈表.xlsx"
)


def _read_payload(path: Path | None) -> dict[str, str]:
    if not path or not path.exists():
        return {}
    data = path.read_text(encoding="utf-8").strip()
    if not data:
        return {}
    return json.loads(data)


def load_config(path: Path | None) -> AppConfig:
    payload = _read_payload(path)
    return AppConfig(
        account=payload.get("account"),
        password=payload.get("password"),
        template_path=Path(payload.get("template_path", DEFAULT_TEMPLATE)),
        output_dir=Path(payload.get("output_dir", ".")),
    )


def ensure_credentials(config: AppConfig, input_fn: Callable[[str], str] = input) -> AppConfig:
    account = config.account or input_fn("手机号: ").strip()
    password = config.password or input_fn("密码: ").strip()
    return replace(config, account=account, password=password)
