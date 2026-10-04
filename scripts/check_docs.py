"""检查本 fork 维护文档的常用 Markdown 本地链接和标题锚点；不执行代码块。"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIRS = (
    "3-1/codebase_agent_demo", "3-1/codebasedemo", "3-2/codebase_agent_demo",
    "3-2/planning_agent_demo", "3-3/planning_agent_demo", "3-5/harness_agent",
)


def prose(text: str) -> str:
    return re.sub(r"^```[^\n]*\n.*?^```\s*$", "", text, flags=re.MULTILINE | re.DOTALL)


def anchors(text: str) -> set[str]:
    result = set()
    counts: dict[str, int] = {}
    for title in re.findall(r"^#{1,6}\s+(.+)$", prose(text), flags=re.MULTILINE):
        slug = re.sub(r"[^\w\- ]", "", title.strip().lower()).replace(" ", "-")
        number = counts.get(slug, 0)
        counts[slug] = number + 1
        result.add(slug if number == 0 else f"{slug}-{number}")
    return result


def documents() -> list[Path]:
    paths = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", *sorted((ROOT / "docs").glob("*.md"))]
    paths += [ROOT / "course_code" / week / "README.md" for week in ("week01", "week02", "week03")]
    paths += [ROOT / "course_code/week03" / name / "README.md" for name in AGENT_DIRS]
    paths += [ROOT / "course_code/week01/1-6/README.md", ROOT / "course_code/week01/1-7/llm-gateway/README.md"]
    paths += [ROOT / "course_code/week02/2-3/README.md"]
    return paths


def main() -> int:
    problems, checked = [], 0
    for path in documents():
        if not path.exists():
            problems.append(f"缺文档：{path.relative_to(ROOT)}")
            continue
        text = prose(path.read_text(encoding="utf-8"))
        for target in re.findall(r"\[[^\]\n]*\]\((<[^>]+>|[^)\s]+)(?:\s+\"[^\"]*\")?\)", text):
            target = target.strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                continue
            checked += 1
            destination = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
            if not destination.exists():
                problems.append(f"{path.relative_to(ROOT)}：不存在 {target}")
            elif (parsed.fragment and destination.suffix == ".md"
                  and unquote(parsed.fragment) not in anchors(destination.read_text(encoding="utf-8"))):
                problems.append(f"{path.relative_to(ROOT)}：标题不存在 {target}")
    for problem in problems:
        print(problem)
    print(f"文档 {len(documents())} 份，本地链接 {checked} 个，错误 {len(problems)} 个")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
