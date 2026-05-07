from .models import Problem, Student, StudentProgress


def _build_rank_map(rank_records: list[dict]) -> dict[str, dict]:
    rank_map: dict[str, dict] = {}
    for record in rank_records:
        uid = record.get("uid")
        if uid is None:
            continue
        rank_map[str(uid)] = record
    return rank_map


def _build_completion_map(
    rank_map: dict[str, dict],
    student: Student,
    problems: list[Problem],
) -> dict[str, str]:
    submission_info_raw = rank_map.get(str(student.uid), {}).get("submissionInfo")
    submission_info = submission_info_raw if isinstance(submission_info_raw, dict) else {}
    completion: dict[str, str] = {}
    for problem in problems:
        info = submission_info.get(problem.problem_id)
        completion[problem.problem_id] = "✅" if info and info.get("isAC") else ""
    return completion


def build_progress_rows(
    students: list[Student],
    problems: list[Problem],
    rank_records: list[dict],
    after_class_problems: list[Problem] | None = None,
    after_class_rank_records: list[dict] | None = None,
) -> list[StudentProgress]:
    rank_map = _build_rank_map(rank_records)
    after_class_rank_map = _build_rank_map(after_class_rank_records or [])
    rows: list[StudentProgress] = []
    for student in students:
        rows.append(
            StudentProgress(
                student=student,
                completion_by_problem=_build_completion_map(rank_map, student, problems),
                after_class_completion_by_problem=_build_completion_map(
                    after_class_rank_map,
                    student,
                    after_class_problems or [],
                ),
            )
        )
    return rows
