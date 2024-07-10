from pathlib import Path


def is_safe_path(base_dir: Path, path: str) -> bool:
    if ".." in path:
        return False
    base_dir = base_dir.resolve()
    user_path = (base_dir / path).resolve()

    return base_dir in user_path.parents
