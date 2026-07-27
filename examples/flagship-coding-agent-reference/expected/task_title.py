"""Expected bounded fix for the flagship coding-agent reference."""


def normalize_task_title(value: str) -> str:
    title = value.strip()
    if not title:
        raise ValueError("Task title must contain visible text.")
    return title
