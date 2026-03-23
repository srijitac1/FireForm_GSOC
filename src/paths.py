"""
Central path resolution module for FireForm.

All path construction goes through this module so the project works correctly
regardless of where it is cloned or run from.
"""

from pathlib import Path


def get_project_root() -> Path:
    """Return the absolute path to the project root directory."""
    # src/paths.py is one level inside the project root
    return Path(__file__).resolve().parent.parent


# Convenience constants
TEMPLATES_DIR: Path = get_project_root() / "src" / "templates"
OUTPUTS_DIR: Path = get_project_root() / "src" / "outputs"


def resolve_path(relative_path: str) -> Path:
    """
    Join the project root with a relative path string.

    Args:
        relative_path: Path relative to the project root, e.g. 'src/templates/fire_dept.pdf'

    Returns:
        Absolute Path object.
    """
    return get_project_root() / relative_path


def to_relative(absolute_path: str) -> str:
    """
    Convert an absolute path to a relative path string from the project root.

    Args:
        absolute_path: Absolute filesystem path string.

    Returns:
        Relative path string using forward slashes, e.g. 'src/templates/fire_dept.pdf'

    Raises:
        ValueError: If the path is not under the project root.
    """
    rel = Path(absolute_path).resolve().relative_to(get_project_root())
    # Always use forward slashes for cross-platform consistency
    return rel.as_posix()
