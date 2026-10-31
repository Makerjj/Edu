from .models import Problem, Student, StudentProgress

ABSENT_TEXT = "请假"


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
        if not isinstance(info, dict):
            completion[problem.problem_id] = ""
            continue

        if info.get("isAC"):
            completion[problem.problem_id] = "✅"
            continue

        status = str(info.get("status", info.get("result", ""))).upper()
        if status in {"PAC", "WA"}:
            completion[problem.problem_id] = status
        elif info.get("isAC") is False:
            try:
                has_partial_score = float(info.get("score", 0)) > 0
            except (TypeError, ValueError):
                has_partial_score = False
            completion[problem.problem_id] = "PAC" if has_partial_score else "WA"
        else:
            completion[problem.problem_id] = ""
    return completion


def build_progress_rows(
    students: list[Student],
    problems: list[Problem],
    rank_records: list[dict],
    after_class_problems: list[Problem] | None = None,
    after_class_rank_records: list[dict] | None = None,
    absent_student_uids: set[str] | None = None,
) -> list[StudentProgress]:
    rank_map = _build_rank_map(rank_records)
    after_class_rank_map = _build_rank_map(after_class_rank_records or [])
    absent_uids = {str(uid) for uid in absent_student_uids or set()}
    rows: list[StudentProgress] = []
    for student in students:
        is_absent = str(student.uid) in absent_uids
        rows.append(
            StudentProgress(
                student=student,
                completion_by_problem=(
                    {problem.problem_id: ABSENT_TEXT for problem in problems}
                    if is_absent
                    else _build_completion_map(rank_map, student, problems)
                ),
                after_class_completion_by_problem=_build_completion_map(
                    after_class_rank_map,
                    student,
                    after_class_problems or [],
                ),
                is_absent=is_absent,
            )
        )
    return rows
