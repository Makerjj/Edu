from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Problem:
    problem_id: str
    title: str


@dataclass(frozen=True)
class Student:
    uid: str
    username: str
    nickname: str


@dataclass(frozen=True)
class Training:
    training_id: int
    title: str


@dataclass(frozen=True)
class Team:
    group_id: int
    name: str


@dataclass(frozen=True)
class ReportRequest:
    team_name: str
    training_name: str
    problem_queries: list[str]
    template_path: Path
    output_dir: Path
    after_class_problem_queries: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StudentProgress:
    student: Student
    completion_by_problem: dict[str, str] = field(default_factory=dict)
    after_class_completion_by_problem: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AppConfig:
    account: str | None
    password: str | None
    template_path: Path
    output_dir: Path
