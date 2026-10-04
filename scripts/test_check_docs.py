"""证明对应检查能发现重命名、失效链接和只存在于注释里的声明。"""
import json

import pytest
from check_docs import check_code_map


@pytest.fixture
def mapped_repo(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src/decision.py").write_text(
        "class Decision:\n    def validate(self):\n        return True\n", encoding="utf-8")
    (tmp_path / "src/runtime.ts").write_text("export class Runtime {}\n", encoding="utf-8")
    (tmp_path / "tests/test_decision.py").write_text("def test_decision(): pass\n", encoding="utf-8")
    (tmp_path / "docs/flow.md").write_text(
        "# 实现\n\n## 校验\n\n"
        "[源码](../src/decision.py) 的 `Decision.validate`。\n"
        "[测试](../tests/test_decision.py) 覆盖校验。\n\n"
        "## 执行\n\n[Runtime](../src/runtime.ts) 和 [测试](../tests/test_decision.py)。\n",
        encoding="utf-8")
    data = {"version": 1, "entries": [
        {"document": "docs/flow.md#校验", "source": "src/decision.py",
         "symbols": ["Decision.validate"], "tests": ["tests/test_decision.py"]},
        {"document": "docs/flow.md#执行", "source": "src/runtime.ts",
         "symbols": ["Runtime"], "tests": ["tests/test_decision.py"]},
    ]}
    (tmp_path / "docs/code-map.json").write_text(json.dumps(data), encoding="utf-8")
    return tmp_path


def test_valid_python_method_and_typescript_export(mapped_repo):
    problems, entries, symbols = check_code_map(mapped_repo)
    assert problems == [] and entries == 2 and symbols == 2


@pytest.mark.parametrize("path,content,expected", [
    ("src/decision.py", "class Decision:\n    def renamed(self): pass\n", "符号不存在"),
    ("src/runtime.ts", "// export class Runtime {}\n", "符号不存在"),
    ("src/runtime.ts", 'const example = `\nexport class Runtime {}\n`;\n', "符号不存在"),
    ("docs/flow.md", "# 只有概述\n", "标题不存在"),
])
def test_stale_mapping_is_rejected(mapped_repo, path, content, expected):
    (mapped_repo / path).write_text(content, encoding="utf-8")
    assert any(expected in problem for problem in check_code_map(mapped_repo)[0])


def test_missing_test_is_rejected(mapped_repo):
    (mapped_repo / "tests/test_decision.py").unlink()
    assert any("测试不存在" in problem for problem in check_code_map(mapped_repo)[0])


def test_symbol_must_appear_in_its_document_section(mapped_repo):
    path = mapped_repo / "docs/flow.md"
    path.write_text(path.read_text().replace("`Decision.validate`", "校验函数"), encoding="utf-8")
    assert any("本节未说明" in problem for problem in check_code_map(mapped_repo)[0])


def test_source_link_must_match_the_document_section(mapped_repo):
    path = mapped_repo / "docs/flow.md"
    path.write_text(path.read_text().replace("[源码](../src/decision.py)", "源码"), encoding="utf-8")
    assert any("本节未链接" in problem for problem in check_code_map(mapped_repo)[0])


def test_mapping_version_is_validated(mapped_repo):
    path = mapped_repo / "docs/code-map.json"
    data = json.loads(path.read_text())
    data["version"] = 99
    path.write_text(json.dumps(data), encoding="utf-8")
    assert any("格式" in problem for problem in check_code_map(mapped_repo)[0])
