"""检查维护文档的链接，以及 code-map 中的源码符号与测试引用；不执行代码块。"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIRS = (
    "3-1/codebase_agent_demo", "3-1/codebasedemo", "3-2/codebase_agent_demo",
    "3-2/planning_agent_demo", "3-3/planning_agent_demo", "3-5/harness_agent",
)
LINK = re.compile(r'\[[^\]\n]*\]\((<[^>]+>|[^)\s]+)(?:\s+"[^"]*")?\)')


def prose(text: str) -> str:
    return re.sub(r"^```[^\n]*\n.*?^```\s*$", "", text, flags=re.MULTILINE | re.DOTALL)


def headings(text: str) -> list[tuple[str, int, int]]:
    """返回 slug、层级和位置；重复标题沿用 Markdown 的编号形式。"""
    result = []
    counts: dict[str, int] = {}
    for match in re.finditer(r"^(#{1,6})\s+(.+)$", text, flags=re.MULTILINE):
        title = match[2]
        slug = re.sub(r"[^\w\- ]", "", title.strip().lower()).replace(" ", "-")
        number = counts.get(slug, 0)
        counts[slug] = number + 1
        result.append((slug if number == 0 else f"{slug}-{number}", len(match[1]), match.start()))
    return result


def anchors(text: str) -> set[str]:
    return {slug for slug, _, _ in headings(prose(text))}


def document_section(text: str, slug: str) -> str | None:
    text = prose(text)
    if not slug:
        return text
    records = headings(text)
    for index, (name, level, start) in enumerate(records):
        if name == slug:
            end = next((position for _, depth, position in records[index + 1:] if depth <= level), len(text))
            return text[start:end]
    return None


def source_symbols(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        symbols: set[str] = set()

        def collect(nodes: list[ast.stmt], prefix: str = "") -> None:
            for node in nodes:
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = prefix + node.name
                    symbols.add(name)
                    collect(node.body, name + ".")

        collect(ast.parse(text).body)
        return symbols
    if path.suffix == ".ts":
        # 仅核对具名 export 声明；屏蔽注释和字符串，避免示例文字被当作源码。
        # 不声称这是 TS 类型检查，实际编译仍由各项目的 tsc 负责。
        literals = r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|//[^\n]*|/\*.*?\*/'''
        text = re.sub(literals, lambda match: re.sub(r"[^\n]", " ", match[0]), text, flags=re.DOTALL)
        return set(re.findall(
            r"^export\s+(?:async\s+)?(?:class|function|interface|type|const|let)\s+([A-Za-z_$][\w$]*)",
            text, flags=re.MULTILINE))
    raise ValueError("只支持 Python 定义和 TypeScript 具名 export")


def check_code_map(root: Path) -> tuple[list[str], int, int]:
    """每条对应关系必须在同一文档小节中说明并链接源码与测试。"""
    root = root.resolve()
    problems: list[str] = []
    try:
        mapping = json.loads((root / "docs/code-map.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"code-map 读取失败：{exc}"], 0, 0
    if not isinstance(mapping, dict) or mapping.get("version") != 1 or not isinstance(mapping.get("entries"), list):
        return ["code-map 格式错误：需要 version=1 和 entries 列表"], 0, 0

    def local_file(relative: str) -> Path | None:
        path = (root / relative).resolve()
        return path if path.is_relative_to(root) and path.is_file() else None

    symbol_count = 0
    for index, entry in enumerate(mapping["entries"], 1):
        if (not isinstance(entry, dict)
            or not all(isinstance(entry.get(key), str) for key in ("document", "source"))
            or not all(isinstance(entry.get(key), list) and entry[key]
                       and all(isinstance(item, str) for item in entry[key]) for key in ("symbols", "tests"))):
            problems.append(f"code-map 第 {index} 条格式错误")
            continue
        document = urlsplit(entry["document"])
        path = local_file(unquote(document.path))
        if path is None or document.scheme or document.netloc:
            problems.append(f"文档不存在：{entry['document']}")
            continue
        section = document_section(path.read_text(encoding="utf-8"), unquote(document.fragment))
        if section is None:
            problems.append(f"标题不存在：{entry['document']}")
            continue
        links = set()
        for target in LINK.findall(section):
            parsed = urlsplit(target.strip("<>"))
            if not parsed.scheme and not parsed.netloc:
                links.add((path.parent / unquote(parsed.path)).resolve())
        source = local_file(entry["source"])
        if source is None:
            problems.append(f"源码不存在：{entry['source']}")
            continue
        try:
            defined = source_symbols(source)
        except (SyntaxError, ValueError) as exc:
            problems.append(f"源码解析失败：{entry['source']}：{exc}")
            continue
        if source not in links:
            problems.append(f"本节未链接源码：{entry['document']} → {entry['source']}")
        for symbol in entry["symbols"]:
            symbol_count += 1
            if symbol not in defined:
                problems.append(f"符号不存在：{entry['source']} → {symbol}")
            if not re.search(r"(?<!\w)" + re.escape(symbol) + r"(?!\w)", section):
                problems.append(f"本节未说明符号：{entry['document']} → {symbol}")
        for test in entry["tests"]:
            test_path = local_file(test)
            if test_path is None:
                problems.append(f"测试不存在：{test}")
            elif test_path not in links:
                problems.append(f"本节未链接测试：{entry['document']} → {test}")
    return problems, len(mapping["entries"]), symbol_count


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
        for target in LINK.findall(text):
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
    mapping_problems, entries, symbols = check_code_map(ROOT)
    problems.extend(mapping_problems)
    for problem in problems:
        print(problem)
    print(f"文档 {len(documents())} 份，本地链接 {checked} 个，对应关系 {entries} 条、源码符号 {symbols} 个，错误 {len(problems)} 个")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
