import json
from pathlib import Path

from src.xdf_report.auth import DingdangAuthClient
from src.xdf_report.config import DEFAULT_TEMPLATE, ensure_credentials, load_config
from src.xdf_report.models import AppConfig


def test_package_entrypoint_exists():
    assert Path("xdf_report.py").exists()
    assert Path("src/xdf_report/models.py").exists()


def test_load_config_reads_defaults(tmp_path: Path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "account": "13800000000",
                "password": "secret",
                "template_path": "/tmp/template.xlsx",
                "output_dir": "/tmp/out",
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.account == "13800000000"
    assert config.password == "secret"
    assert str(config.template_path) == "/tmp/template.xlsx"
    assert str(config.output_dir) == "/tmp/out"


def test_load_config_uses_defaults_when_missing():
    config = load_config(None)

    assert config.account is None
    assert config.password is None
    assert config.template_path == DEFAULT_TEMPLATE
    assert config.output_dir == Path(".")


def test_ensure_credentials_prompts_when_missing():
    prompts = iter(["13800000000", "secret"])

    def fake_input(prompt: str) -> str:
        return next(prompts)

    config = AppConfig(
        account=None,
        password=None,
        template_path=Path("/tmp/template.xlsx"),
        output_dir=Path("/tmp/out"),
    )

    updated = ensure_credentials(config, input_fn=fake_input)

    assert updated.account == "13800000000"
    assert updated.password == "secret"


def test_auth_client_exposes_base_urls():
    client = DingdangAuthClient()
    assert client.dd_base_url.endswith("/api/dingdang")
    assert client.oj_base_url.endswith("/api/oj")
