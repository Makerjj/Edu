#!/usr/bin/env python3
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
VOICEOVER_JSON = PROJECT_ROOT / "src" / "voiceover.json"
VOICEOVER_DURATIONS_JSON = PROJECT_ROOT / "src" / "voiceoverDurations.json"
PUBLIC_AUDIO_DIR = PROJECT_ROOT / "public" / "audio"
EDGE_TTS = PROJECT_ROOT.parent / ".tts_venv" / "bin" / "edge-tts"
VOICE = "zh-CN-YunxiNeural"
RATE = "-10%"
HASH_FILE = PUBLIC_AUDIO_DIR / ".voiceover-hash"
FORCE_REGENERATE = os.getenv("FORCE_VOICEOVER_REGEN") == "1"


def audio_duration(path: Path) -> float:
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
    ).strip()
    return float(out)


def run(cmd):
    subprocess.run(cmd, check=True)


def file_ok(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 1000


def clear_audio_dir() -> None:
    if not PUBLIC_AUDIO_DIR.exists():
        return
    for stale in PUBLIC_AUDIO_DIR.rglob("*"):
        if stale.is_file():
            stale.unlink()
    for stale_dir in sorted((p for p in PUBLIC_AUDIO_DIR.rglob("*") if p.is_dir()), reverse=True):
        try:
            stale_dir.rmdir()
        except OSError:
            pass
    try:
        PUBLIC_AUDIO_DIR.rmdir()
    except OSError:
        pass


def main():
    config = json.loads(VOICEOVER_JSON.read_text(encoding="utf-8"))
    payload = json.dumps(
        {"voice": VOICE, "rate": RATE, "config": config},
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()

    expected_files = [PROJECT_ROOT / "public" / item["audio"] for item in config.values()]
    if (
        not FORCE_REGENERATE
        and HASH_FILE.exists()
        and HASH_FILE.read_text(encoding="utf-8").strip() == digest
        and all(file_ok(p) for p in expected_files)
    ):
        print("Voiceover is up to date.")
        return

    clear_audio_dir()
    PUBLIC_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    durations = {}
    for name, item in config.items():
        out = PROJECT_ROOT / "public" / item["audio"]
        out.parent.mkdir(parents=True, exist_ok=True)
        print(f"Generating {name}: {out.name}")
        for attempt in range(1, 4):
            try:
                run(
                    [
                        str(EDGE_TTS),
                        "--voice",
                        VOICE,
                        f"--rate={RATE}",
                        "--text",
                        item["text"],
                        "--write-media",
                        str(out),
                    ]
                )
            except subprocess.CalledProcessError:
                if attempt == 3:
                    raise RuntimeError(f"Could not generate audio for {name} with edge-tts")
                time.sleep(attempt * 2)
                continue
            if file_ok(out):
                break
        if not file_ok(out):
            raise RuntimeError(f"edge-tts did not create audio: {out}")
        durations[name] = audio_duration(out)

    HASH_FILE.write_text(f"{digest}\n", encoding="utf-8")
    VOICEOVER_DURATIONS_JSON.write_text(
        json.dumps(durations, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("Voiceover generation finished.")


if __name__ == "__main__":
    main()
