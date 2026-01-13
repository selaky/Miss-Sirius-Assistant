"""
pipeline 节点 next 优先级检查工具

检查每个节点的 next 列表是否按正确的优先级顺序排列。
优先级从高到低：
1. 意外处理（连接到"意外处理"节点）
2. 有条件自我循环（有条件节点且 next 连接自身）
3. 有条件节点（非 DirectHit）
4. 无条件节点（DirectHit）

用法示例：
  python my_tools/check_priority.py
  python my_tools/check_priority.py --strict  # 严格模式
"""

from __future__ import annotations

import argparse
import json
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Optional


# ============================================================================
# 优先级规则定义（易于扩展）
# ============================================================================

@dataclass
class PriorityRule:
    """
    优先级规则定义。

    Attributes:
        name: 规则名称（用于输出）
        priority: 优先级数值，越小优先级越高
        matcher: 匹配函数，签名为 (current_node_name, current_node_obj, ref_name, all_nodes) -> bool
    """
    name: str
    priority: int
    matcher: Callable[[str, dict, str, dict[str, dict]], bool]


def _is_conditional_node(node_obj: dict) -> bool:
    """判断节点是否为有条件节点（非 DirectHit）"""
    recognition = node_obj.get("recognition")
    if not isinstance(recognition, dict):
        return True  # 没有 recognition 字段，默认视为有条件
    rec_type = recognition.get("type", "")
    return rec_type != "DirectHit"


def _is_unconditional_node(node_obj: dict) -> bool:
    """判断节点是否为无条件节点（DirectHit）"""
    return not _is_conditional_node(node_obj)


def _get_ref_name(ref: Any) -> Optional[str]:
    """从引用项中提取节点名"""
    if isinstance(ref, str):
        return ref
    if isinstance(ref, dict):
        return ref.get("name")
    return None


# ============================================================================
# 内置优先级规则
# ============================================================================

def match_exception_handler(
    current_node_name: str,
    current_node_obj: dict,
    ref_name: str,
    all_nodes: dict[str, dict]
) -> bool:
    """规则：意外处理（连接到"意外处理"节点）"""
    return ref_name == "意外处理"


def match_conditional_self_loop(
    current_node_name: str,
    current_node_obj: dict,
    ref_name: str,
    all_nodes: dict[str, dict]
) -> bool:
    """规则：有条件自我循环（有条件节点且 next 连接自身）"""
    if ref_name != current_node_name:
        return False
    return _is_conditional_node(current_node_obj)


def match_conditional_node(
    current_node_name: str,
    current_node_obj: dict,
    ref_name: str,
    all_nodes: dict[str, dict]
) -> bool:
    """规则：有条件节点（引用的目标节点是有条件的）"""
    target_node = all_nodes.get(ref_name)
    if target_node is None:
        return False  # 目标节点不存在，跳过
    return _is_conditional_node(target_node)


def match_unconditional_node(
    current_node_name: str,
    current_node_obj: dict,
    ref_name: str,
    all_nodes: dict[str, dict]
) -> bool:
    """规则：无条件节点（引用的目标节点是 DirectHit）"""
    target_node = all_nodes.get(ref_name)
    if target_node is None:
        return False  # 目标节点不存在，跳过
    return _is_unconditional_node(target_node)


# 默认优先级规则列表（按优先级从高到低排列）
# 要添加新规则，只需在此列表中插入新的 PriorityRule
DEFAULT_PRIORITY_RULES: list[PriorityRule] = [
    PriorityRule(
        name="意外处理",
        priority=1,
        matcher=match_exception_handler,
    ),
    PriorityRule(
        name="有条件自我循环",
        priority=2,
        matcher=match_conditional_self_loop,
    ),
    PriorityRule(
        name="有条件节点",
        priority=3,
        matcher=match_conditional_node,
    ),
    PriorityRule(
        name="无条件节点",
        priority=4,
        matcher=match_unconditional_node,
    ),
]


# ============================================================================
# 优先级检查器
# ============================================================================

@dataclass(frozen=True)
class PriorityIssue:
    """优先级问题"""
    level: Literal["ERROR", "WARN"]
    node_name: str
    file_path: Optional[Path]
    message: str
    current_order: list[str] = field(default_factory=list)
    expected_order: list[str] = field(default_factory=list)

    def format(self) -> str:
        loc = []
        if self.file_path:
            loc.append(str(self.file_path.as_posix()))
        loc.append(f"节点={self.node_name}")
        suffix = f" ({', '.join(loc)})"

        lines = [f"[{self.level}] {self.message}{suffix}"]
        if self.current_order:
            lines.append(f"  当前顺序: {' -> '.join(self.current_order)}")
        if self.expected_order:
            lines.append(f"  建议顺序: {' -> '.join(self.expected_order)}")
        return "\n".join(lines)


class PriorityChecker:
    """优先级检查器"""

    def __init__(self, rules: list[PriorityRule] | None = None):
        self.rules = rules or DEFAULT_PRIORITY_RULES
        # 按优先级排序规则
        self.rules = sorted(self.rules, key=lambda r: r.priority)

    def get_priority(
        self,
        current_node_name: str,
        current_node_obj: dict,
        ref_name: str,
        all_nodes: dict[str, dict]
    ) -> tuple[int, str]:
        """
        获取引用的优先级。

        Returns:
            (优先级数值, 规则名称)
        """
        for rule in self.rules:
            if rule.matcher(current_node_name, current_node_obj, ref_name, all_nodes):
                return (rule.priority, rule.name)
        # 未匹配任何规则，返回最低优先级
        return (999, "未知")

    def check_node(
        self,
        node_name: str,
        node_obj: dict,
        all_nodes: dict[str, dict],
        file_path: Optional[Path] = None
    ) -> list[PriorityIssue]:
        """检查单个节点的 next 优先级顺序"""
        issues: list[PriorityIssue] = []

        next_field = node_obj.get("next")
        if not next_field:
            return issues

        # 确保 next 是列表
        if not isinstance(next_field, list):
            next_field = [next_field]

        # 提取所有引用名称和对应的优先级
        refs_with_priority: list[tuple[str, int, str]] = []  # (ref_name, priority, rule_name)

        for ref in next_field:
            ref_name = _get_ref_name(ref)
            if not ref_name:
                continue
            priority, rule_name = self.get_priority(node_name, node_obj, ref_name, all_nodes)
            refs_with_priority.append((ref_name, priority, rule_name))

        if len(refs_with_priority) < 2:
            return issues  # 只有一个或零个引用，无需检查顺序

        # 检查是否按优先级从高到低排列
        is_sorted = True
        for i in range(len(refs_with_priority) - 1):
            if refs_with_priority[i][1] > refs_with_priority[i + 1][1]:
                is_sorted = False
                break

        if not is_sorted:
            # 生成当前顺序和建议顺序
            current_order = [f"{name}({rule})" for name, _, rule in refs_with_priority]
            sorted_refs = sorted(refs_with_priority, key=lambda x: x[1])
            expected_order = [f"{name}({rule})" for name, _, rule in sorted_refs]

            issues.append(PriorityIssue(
                level="WARN",
                node_name=node_name,
                file_path=file_path,
                message="next 列表优先级顺序不正确",
                current_order=current_order,
                expected_order=expected_order,
            ))

        return issues


# ============================================================================
# 文件加载工具
# ============================================================================

def load_json_file(path: Path) -> tuple[Optional[dict], Optional[str]]:
    """加载 JSON 文件，返回 (对象, 错误信息)"""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (UnicodeDecodeError, OSError) as e:
        return None, f"读取文件失败：{e}"

    try:
        obj = json.loads(text)
        return obj, None
    except json.JSONDecodeError as e:
        return None, f"JSON 解析失败：{e}"


def collect_all_nodes(pipeline_dir: Path) -> tuple[dict[str, dict], dict[str, Path]]:
    """
    收集所有 pipeline 文件中的节点。

    Returns:
        (节点名 -> 节点对象, 节点名 -> 文件路径)
    """
    all_nodes: dict[str, dict] = {}
    node_to_file: dict[str, Path] = {}

    for json_file in pipeline_dir.glob("**/*.json"):
        if not json_file.is_file():
            continue

        obj, err = load_json_file(json_file)
        if err or not isinstance(obj, dict):
            continue

        for key, value in obj.items():
            # 跳过编辑器元数据
            if isinstance(key, str) and key.startswith("$"):
                continue
            if not isinstance(key, str) or not key.strip():
                continue
            if not isinstance(value, dict):
                continue

            if key not in all_nodes:
                all_nodes[key] = value
                node_to_file[key] = json_file

    return all_nodes, node_to_file


# ============================================================================
# 主函数
# ============================================================================

def main(argv: list[str]) -> int:
    # UTF-8 输出
    if hasattr(sys.stdout, "reconfigure"):
        try:
            if (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
                sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="检查 pipeline 节点 next 列表的优先级顺序是否正确"
    )
    parser.add_argument(
        "--pipeline-dir",
        default="assets/resource/pipeline",
        help="pipeline 目录（默认：assets/resource/pipeline）",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="严格模式：将 WARN 也视为失败（返回非 0）",
    )
    parser.add_argument(
        "--show-rules",
        action="store_true",
        help="显示当前的优先级规则列表",
    )
    args = parser.parse_args(argv)

    # 显示规则列表
    if args.show_rules:
        print("当前优先级规则（从高到低）：")
        for rule in DEFAULT_PRIORITY_RULES:
            print(f"  {rule.priority}. {rule.name}")
        return 0

    pipeline_dir = Path(args.pipeline_dir)

    if not pipeline_dir.exists():
        print(f"[ERROR] pipeline 目录不存在：{pipeline_dir}")
        return 2

    # 收集所有节点
    all_nodes, node_to_file = collect_all_nodes(pipeline_dir)

    if not all_nodes:
        print(f"[ERROR] 未找到任何节点")
        return 2

    # 检查优先级
    checker = PriorityChecker()
    all_issues: list[PriorityIssue] = []

    for node_name, node_obj in all_nodes.items():
        file_path = node_to_file.get(node_name)
        issues = checker.check_node(node_name, node_obj, all_nodes, file_path)
        all_issues.extend(issues)

    # 输出结果
    errors = [i for i in all_issues if i.level == "ERROR"]
    warns = [i for i in all_issues if i.level == "WARN"]

    for issue in all_issues:
        print(issue.format())
        print()

    print(f"检查完成：节点 {len(all_nodes)} 个，ERROR {len(errors)}，WARN {len(warns)}")

    if errors:
        return 1
    if args.strict and warns:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
