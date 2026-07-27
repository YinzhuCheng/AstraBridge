from task_title import normalize_task_title


def main() -> None:
    assert normalize_task_title("  Fix release notes  ") == "Fix release notes"
    try:
        normalize_task_title("   ")
    except ValueError:
        return
    raise AssertionError("Whitespace-only task titles must be rejected.")


if __name__ == "__main__":
    main()
