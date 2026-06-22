#!/usr/bin/env python3
import argparse
import math
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parent.parent
REMOTION_SHARED = ROOT / "scripts" / "remotion_shared.py"
DEFAULT_FORBIDDEN = [
    "PrimeComposite",
    "prime-composite",
    "找素数",
    "素数",
    "质数",
    "isPrime",
    "int A",
    "int B",
]
FRAME_SCENES = ["intro", "sample", "strategy", "code", "summary"]
FPS = 30
STORYBOARD_REQUIRED_FIELDS = ["id", "scene", "title", "visual", "narration", "subtitle"]


@dataclass(frozen=True)
class ProjectConfig:
    project_dir: Path
    package_name: str
    composition: str
    entry: str
    output: str
    draft_output: str
    scenes: list[str]
    forbidden: list[str]


def run(cmd: list[str], cwd: Path = ROOT, capture: bool = False) -> subprocess.CompletedProcess[str]:
    print("$ " + " ".join(cmd))
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_package_render(package_json: dict) -> tuple[str, str, str]:
    render = package_json.get("scripts", {}).get("render", "")
    match = re.search(r"render\s+(\S+)\s+(\S+)\s+(\S+)", render)
    if not match:
        raise SystemExit("Could not parse render script. Expected `... render <entry> <composition> <output>`.")
    return match.group(1), match.group(2), match.group(3)


def load_config(project: str) -> ProjectConfig:
    project_dir = ROOT / project
    if not project_dir.exists():
        raise SystemExit(f"Project not found: {project}")
    package_json_path = project_dir / "package.json"
    if not package_json_path.exists():
        raise SystemExit(f"Missing package.json: {project}")
    package_json = load_json(package_json_path)
    entry, composition, output = parse_package_render(package_json)
    contract_path = project_dir / "artifact_contract.json"
    contract = load_json(contract_path) if contract_path.exists() else {}
    forbidden = list(dict.fromkeys([*DEFAULT_FORBIDDEN, *contract.get("forbiddenResidue", [])]))
    output = contract.get("output", output)
    scenes = contract.get("scenes") or contract.get("requiredScenes") or FRAME_SCENES
    output_path = Path(output)
    draft_output = str(output_path.with_name(f"{output_path.stem}.draft{output_path.suffix}"))
    return ProjectConfig(
        project_dir=project_dir,
        package_name=package_json.get("name", project),
        composition=contract.get("composition", composition),
        entry=contract.get("entry", entry),
        output=output,
        draft_output=contract.get("draftOutput", draft_output),
        scenes=scenes,
        forbidden=forbidden,
    )


def iter_source_files(project_dir: Path):
    allowed_suffixes = {".ts", ".tsx", ".json", ".md", ".js", ".mjs", ".py"}
    for path in project_dir.rglob("*"):
        if "node_modules" in path.parts or path.is_dir():
            continue
        if path.suffix in allowed_suffixes:
            yield path


def check_forbidden(config: ProjectConfig) -> list[str]:
    findings: list[str] = []
    output_path = config.project_dir / config.output
    draft_output_path = config.project_dir / config.draft_output
    contract_path = config.project_dir / "artifact_contract.json"
    for path in iter_source_files(config.project_dir):
        if path == contract_path:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for term in config.forbidden:
            if term and term in text:
                findings.append(f"{path.relative_to(ROOT)} contains forbidden residue: {term}")
    for path in (config.project_dir / "out").glob("*") if (config.project_dir / "out").exists() else []:
        if path.is_file() and path not in {output_path, draft_output_path}:
            findings.append(f"stale output file: {path.relative_to(ROOT)}")
    return findings


def check_required_files(config: ProjectConfig) -> list[str]:
    findings: list[str] = []
    for rel in ["src/Root.tsx", "src/index.ts", "src/lessonData.ts", "src/voiceover.json", "src/timing.ts"]:
        if not (config.project_dir / rel).exists():
            findings.append(f"missing required file: {config.project_dir.relative_to(ROOT)}/{rel}")
    if not (config.project_dir / config.entry).exists():
        findings.append(f"render entry does not exist: {config.entry}")
    root_text = (config.project_dir / "src" / "Root.tsx").read_text(encoding="utf-8", errors="ignore")
    if config.composition not in root_text:
        findings.append(f"composition `{config.composition}` not found in src/Root.tsx")
    return findings


def validate_storyboard(project_dir: Path) -> list[str]:
    storyboard_path = project_dir / "storyboard.json"
    if not storyboard_path.exists():
        return []
    try:
        storyboard = load_json(storyboard_path)
    except json.JSONDecodeError as exc:
        return [f"storyboard.json is invalid JSON: {exc.msg}"]
    shots = storyboard.get("shots")
    if not isinstance(shots, list) or not shots:
        return ["storyboard.json field `shots` must be a non-empty list"]
    findings: list[str] = []
    seen_ids: set[str] = set()
    for index, shot in enumerate(shots, start=1):
        if not isinstance(shot, dict):
            findings.append(f"shot #{index} must be an object")
            continue
        shot_id = str(shot.get("id") or f"#{index}")
        if shot_id in seen_ids:
            findings.append(f"shot {shot_id} duplicates a previous shot id")
        seen_ids.add(shot_id)
        for field in STORYBOARD_REQUIRED_FIELDS:
            value = shot.get(field)
            if not isinstance(value, str) or not value.strip():
                findings.append(f"shot {shot_id} missing required field: {field}")
        duration_hint = shot.get("durationHint")
        if duration_hint is not None and (
            not isinstance(duration_hint, (int, float)) or duration_hint <= 0
        ):
            findings.append(f"shot {shot_id} field `durationHint` must be a positive number")
        checks = shot.get("checks")
        if checks is not None and not isinstance(checks, list):
            findings.append(f"shot {shot_id} field `checks` must be a list")
    return findings


def command_check(config: ProjectConfig, skip_tsc: bool = False) -> None:
    findings = [
        *check_required_files(config),
        *check_forbidden(config),
        *validate_storyboard(config.project_dir),
    ]
    if findings:
        print("Check failed:")
        for item in findings:
            print(f"- {item}")
        raise SystemExit(1)
    if not skip_tsc:
        run(["npx", "tsc", "--noEmit"], cwd=config.project_dir)
    print("Check passed.")


def command_storyboard(config: ProjectConfig) -> None:
    storyboard_path = config.project_dir / "storyboard.json"
    if not storyboard_path.exists():
        raise SystemExit(f"Missing storyboard.json: {config.project_dir.relative_to(ROOT)}")
    findings = validate_storyboard(config.project_dir)
    if findings:
        print("Storyboard check failed:")
        for item in findings:
            print(f"- {item}")
        raise SystemExit(1)
    shot_count = len(load_json(storyboard_path)["shots"])
    print(f"Storyboard check passed: {shot_count} shots.")


def ensure_voiceover(config: ProjectConfig) -> None:
    package_json = load_json(config.project_dir / "package.json")
    if "voiceover" in package_json.get("scripts", {}):
        run(["npm", "run", "voiceover"], cwd=config.project_dir)


def read_fixed_frame_count(timing_text: str, name: str) -> Optional[int]:
    duration_match = re.search(rf"{re.escape(name)}\s*:\s*([A-Za-z_][A-Za-z0-9_]*)", timing_text)
    if not duration_match:
        return None
    variable = duration_match.group(1)
    variable_match = re.search(rf"const\s+{re.escape(variable)}\s*=\s*(\d+)\s*\*\s*fps", timing_text)
    if variable_match:
        return int(variable_match.group(1)) * FPS
    return None


def read_scene_timeline(config: ProjectConfig) -> tuple[dict[str, int], dict[str, int]]:
    timing_path = config.project_dir / "src" / "timing.ts"
    timing_text = timing_path.read_text(encoding="utf-8", errors="ignore")
    durations_path = config.project_dir / "src" / "voiceoverDurations.json"
    if not durations_path.exists():
        starts = {name: index * 240 for index, name in enumerate(config.scenes)}
        durations = {name: 240 for name in config.scenes}
        return starts, durations
    durations = load_json(durations_path)
    order = config.scenes
    starts: dict[str, int] = {}
    scene_durations: dict[str, int] = {}
    frame = 0
    for name in order:
        starts[name] = frame
        if name in durations:
            duration = math.ceil(float(durations[name]) * FPS) + 18
        else:
            duration = read_fixed_frame_count(timing_text, name) or 150
        scene_durations[name] = duration
        frame += duration
    if "code" not in starts and order:
        starts["code"] = max(0, frame - 300)
    if "summary" not in starts and order:
        starts["summary"] = max(0, frame - 120)
    return starts, scene_durations


def sample_frame(name: str, start: int, duration: int) -> int:
    if duration <= 1:
        return start
    if name == "code":
        offset = min(max(180, duration // 2), duration - 1)
        return start + offset
    offset = min(90, max(15, duration // 3))
    return start + min(offset, duration - 1)


def command_frames(config: ProjectConfig, skip_check: bool = False) -> None:
    if not skip_check:
        command_check(config)
    ensure_voiceover(config)
    starts, durations = read_scene_timeline(config)
    frame_dir = Path(tempfile.gettempdir()) / f"{config.project_dir.name}_frames"
    if frame_dir.exists():
        shutil.rmtree(frame_dir)
    frame_dir.mkdir(parents=True, exist_ok=True)
    for name in config.scenes:
        frame = sample_frame(name, starts.get(name, 0), durations.get(name, 240))
        out = frame_dir / f"{name}.png"
        run(
            [
                "python3",
                str(REMOTION_SHARED),
                "still",
                config.entry,
                config.composition,
                str(out),
                "--frame",
                str(frame),
            ],
            cwd=config.project_dir,
        )
    print(f"Frames written to {frame_dir}")


def command_draft(config: ProjectConfig, skip_check: bool = False) -> None:
    if not skip_check:
        command_check(config)
    ensure_voiceover(config)
    run(
        [
            "python3",
            str(REMOTION_SHARED),
            "render",
            config.entry,
            config.composition,
            config.draft_output,
            "--codec",
            "h264",
            "--crf",
            "28",
            "--x264-preset",
            "ultrafast",
            "--jpeg-quality",
            "70",
            "--scale",
            "0.5",
        ],
        cwd=config.project_dir,
    )
    output_path = config.project_dir / config.draft_output
    run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size",
            "-show_streams",
            "-of",
            "json",
            str(output_path),
        ]
    )
    print(f"Draft video: {output_path.relative_to(ROOT)}")


def command_final(config: ProjectConfig, skip_check: bool = False) -> None:
    if not skip_check:
        command_check(config)
    run(["npm", "run", "render"], cwd=config.project_dir)
    output_path = config.project_dir / config.output
    run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size",
            "-show_streams",
            "-of",
            "json",
            str(output_path),
        ]
    )
    print(f"Final video: {output_path.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-lesson Remotion video workflow")
    parser.add_argument("command", choices=["storyboard", "check", "frames", "draft", "final"])
    parser.add_argument("project", help="Project directory under Edu/pre_lesson, for example remotion_beautiful_numbers")
    parser.add_argument("--skip-check", action="store_true")
    parser.add_argument("--skip-tsc", action="store_true")
    args = parser.parse_args()

    config = load_config(args.project)
    if args.command == "storyboard":
        command_storyboard(config)
    elif args.command == "check":
        command_check(config, skip_tsc=args.skip_tsc)
    elif args.command == "frames":
        command_frames(config, skip_check=args.skip_check)
    elif args.command == "draft":
        command_draft(config, skip_check=args.skip_check)
    elif args.command == "final":
        command_final(config, skip_check=args.skip_check)
    else:
        raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
