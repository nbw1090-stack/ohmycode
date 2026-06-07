"""样本项目工厂 — 在临时目录中创建确定性的样本项目。

用于评估测试的可复现工作区。所有文件内容都是确定性的，
便于对文件内容、搜索结果进行精确断言。
"""

from pathlib import Path


# ===== 样本文件内容（确定性）=====

MAIN_PY = '''"""主程序入口 — 包含一个 off-by-one bug。"""


def greet(names: list[str]) -> list[str]:
    """向列表中的每个人打招呼。

    Bug: range 上界应该是 len(names) 而不是 len(names) - 1，
    导致最后一个名字被跳过。
    """
    results = []
    for i in range(len(names) - 1):  # BUG: off-by-one
        results.append(f"Hello, {names[i]}!")
    return results


def calculate_sum(numbers: list[int]) -> int:
    """计算整数列表的总和。"""
    total = 0
    for n in numbers:
        total += n
    return total


def main():
    users = ["Alice", "Bob", "Charlie"]
    greetings = greet(users)
    for g in greetings:
        print(g)

    numbers = [1, 2, 3, 4, 5]
    print(f"Sum: {calculate_sum(numbers)}")


if __name__ == "__main__":
    main()
'''

UTILS_PY = '''"""工具函数集 — 辅助数据处理函数。"""

import json
from typing import Any


def calculate(a: int, b: int, op: str = "add") -> int:
    """简单的计算器函数。

    Args:
        a: 第一个操作数
        b: 第二个操作数
        op: 运算类型 (add, sub, mul)

    Returns:
        计算结果
    """
    if op == "add":
        return a + b
    elif op == "sub":
        return a - b
    elif op == "mul":
        return a * b
    else:
        raise ValueError(f"未知运算: {op}")


def format_data(data: dict[str, Any]) -> str:
    """将字典格式化为 JSON 字符串。"""
    return json.dumps(data, indent=2, ensure_ascii=False)


def process_data(items: list[str]) -> dict[str, int]:
    """处理字符串列表，返回每个字符串的长度映射。"""
    return {item: len(item) for item in items}


def validate_input(value: str, min_length: int = 1) -> bool:
    """验证输入字符串是否满足最小长度要求。"""
    return len(value.strip()) >= min_length
'''

CONFIG_JSON = '''{
    "app_name": "ohmycode-demo",
    "version": "1.0.0",
    "debug": true,
    "database": {
        "host": "localhost",
        "port": 5432,
        "name": "demo_db"
    },
    "features": {
        "logging": true,
        "metrics": false,
        "auth": true
    }
}'''

TEST_MAIN_PY = '''"""main.py 的基本测试。"""

from main import greet, calculate_sum


def test_greet():
    names = ["Alice", "Bob", "Charlie"]
    result = greet(names)
    # 注意：由于 off-by-one bug，这里只有 2 个结果而非 3 个
    assert len(result) == 2  # 这个测试反映了当前 bug 行为


def test_calculate_sum():
    assert calculate_sum([1, 2, 3]) == 6
    assert calculate_sum([]) == 0
    assert calculate_sum([-1, 1]) == 0
'''

README_MD = """# ohmycode-demo

A sample project for evaluation testing.

## Structure

- `main.py` — 主程序入口
- `utils.py` — 工具函数集
- `config.json` — 配置文件
- `tests/` — 测试目录

## Usage

```bash
python main.py
```

## TODO

- Fix the off-by-one bug in greet()
- Add more test cases
- Add logging support
"""


def create_sample_project(root: Path) -> Path:
    """在指定目录下创建样本项目。

    Args:
        root: 临时目录的根路径

    Returns:
        样本项目的根路径（root 本身）
    """
    root.mkdir(parents=True, exist_ok=True)

    # 创建顶层文件
    (root / "main.py").write_text(MAIN_PY, encoding="utf-8")
    (root / "utils.py").write_text(UTILS_PY, encoding="utf-8")
    (root / "config.json").write_text(CONFIG_JSON, encoding="utf-8")
    (root / "README.md").write_text(README_MD, encoding="utf-8")

    # 创建 tests 子目录
    tests_dir = root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_main.py").write_text(TEST_MAIN_PY, encoding="utf-8")
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")

    return root
