"""Parent-template hook: rebuild research inputs before rendering."""

from pathlib import Path
import sys


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project / "src"))
    from skillarum.publication import build_research_package

    build_research_package(project, project / "output")


if __name__ == "__main__":
    main()
