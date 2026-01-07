"""
pipeline 快速自检脚本

解决的问题（优先级从高到低）：
1) 悬空引用：next / on_error / interrupt 引用了不存在的节点或锚点
2) 重复节点：同一个节点名在多个 pipeline 文件中重复定义
3) 常见资源缺失：TemplateMatch/FeatureMatch 的模板图片路径不存在
4) 任务入口校验：interface.json 的 task.entry 指向不存在的节点

用法示例：
  python my_tools/check_pipeline.py
  python my_tools/check_pipeline.py --strict 严格模式（有 WARN 也返回非 0）
  python my_tools/check_pipeline.py --no-unreachable 不提示“可能未触达的遗留节点”
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Optional, Tuple


Level = Literal["ERROR", "WARN", "INFO"]
RefKind = Literal["node", "anchor"]


@dataclass(frozen=True)
class Issue:
    level: Level
    code: str
    message: str
    file: Optional[Path] = None
    node: Optional[str] = None
    field: Optional[str] = None

    def format_one_line(self) -> str:
        loc = []
        if self.file is not None:
            loc.append(str(self.file.as_posix()))
        if self.node is not None:
            loc.append(f"节点={self.node}")
        if self.field is not None:
            loc.append(f"字段={self.field}")
        suffix = f" ({', '.join(loc)})" if loc else ""
        return f"[{self.level}][{self.code}] {self.message}{suffix}"


@dataclass(frozen=True)
class NodeRef:
    kind: RefKind
    name: str
    raw: Any


def _ensure_list(v: Any) -> list[Any]:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def _strip_jsonc(text: str) -> str:
    """
    尽量安全地移除 JSONC 注释（// 与 /* */），不破坏字符串内容。

    说明：
    - 这是一个轻量实现，不做 JSON5 那样的“允许尾随逗号”等扩展。
    - 对于本仓库的 interface.json（JSON + 注释）足够使用。
    """

    out: list[str] = []
    i = 0
    n = len(text)
    in_string = False
    escape = False
    in_line_comment = False
    in_block_comment = False

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
                out.append(ch)
            i += 1
            continue

        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue

        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == "\"":
                in_string = False
            i += 1
            continue

        # 非字符串区域：识别注释起始
        if ch == "/" and nxt == "/":
            in_line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue

        out.append(ch)
        if ch == "\"":
            in_string = True
        i += 1

    return "".join(out)


def _load_json_file(path: Path) -> Tuple[Optional[Any], list[str], Optional[str]]:
    """
    返回： (对象, 重复 key 列表, 解析错误文本)
    - 若解析失败，对象为 None，错误文本不为 None。
    """
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as e:
        return None, [], f"文件编码不是 UTF-8（或包含非法字节）：{e}"
    except OSError as e:
        return None, [], f"读取文件失败：{e}"

    duplicate_keys: list[str] = []

    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        seen: set[str] = set()
        obj: dict[str, Any] = {}
        for k, v in pairs:
            if k in seen:
                duplicate_keys.append(k)
            seen.add(k)
            obj[k] = v
        return obj

    try:
        obj = json.loads(text, object_pairs_hook=hook)
    except json.JSONDecodeError as e:
        return None, duplicate_keys, f"JSON 语法错误：{e}"

    return obj, duplicate_keys, None


def _load_jsonc_file(path: Path) -> Tuple[Optional[Any], Optional[str]]:
    """
    返回： (对象, 解析错误文本)
    """
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as e:
        return None, f"文件编码不是 UTF-8（或包含非法字节）：{e}"
    except OSError as e:
        return None, f"读取文件失败：{e}"

    try:
        import jsonc  # type: ignore
    except ModuleNotFoundError:
        jsonc = None

    if jsonc is not None:
        try:
            with path.open("r", encoding="utf-8") as f:
                return jsonc.load(f), None
        except Exception as e:  # noqa: BLE001 - 这里用于容错提示
            return None, f"json-with-comments 解析失败：{e}"

    stripped = _strip_jsonc(text)
    try:
        return json.loads(stripped), None
    except json.JSONDecodeError as e:
        return None, f"JSONC 解析失败（未安装 json-with-comments，且内置解析不支持某些语法）：{e}"


def _iter_refs_in_field(value: Any) -> Iterable[NodeRef]:
    """
    解析 next/on_error/interrupt 字段的引用项，兼容：
    - string: 可能带前缀，如 [JumpBack]节点名 / [Anchor]锚点名
    - object: NodeAttr 形式，如 {"name": "...", "jump_back": true} 或 {"name": "...", "anchor": true}
    - list: 以上混合数组
    """
    if value is None:
        return []

    def parse_string_ref(s: str) -> NodeRef:
        prefixes: list[str] = []
        rest = s
        while rest.startswith("["):
            m = re.match(r"^\[([^\]]+)\]", rest)
            if not m:
                break
            prefixes.append(m.group(1))
            rest = rest[m.end() :]

        if any(p.lower() == "anchor" for p in prefixes):
            return NodeRef(kind="anchor", name=rest, raw=s)
        return NodeRef(kind="node", name=rest, raw=s)

    out: list[NodeRef] = []

    def walk(v: Any) -> None:
        if v is None:
            return
        if isinstance(v, str):
            out.append(parse_string_ref(v))
            return
        if isinstance(v, dict):
            name = v.get("name")
            if isinstance(name, str):
                if v.get("anchor") is True:
                    out.append(NodeRef(kind="anchor", name=name, raw=v))
                else:
                    out.append(NodeRef(kind="node", name=name, raw=v))
            return
        if isinstance(v, list):
            for it in v:
                walk(it)
            return

    walk(value)
    return out


def _collect_templates_from_node(node_obj: Any) -> list[str]:
    """
    仅做“常见场景”的模板资源校验：
    - recognition: { type, param: { template: [...] } }
    """
    if not isinstance(node_obj, dict):
        return []
    rec = node_obj.get("recognition")
    if not isinstance(rec, dict):
        return []
    param = rec.get("param")
    if not isinstance(param, dict):
        return []
    templates = param.get("template")
    out: list[str] = []
    for t in _ensure_list(templates):
        if isinstance(t, str):
            out.append(t)
    return out


def _collect_anchor_definitions(node_obj: Any) -> list[str]:
    if not isinstance(node_obj, dict):
        return []
    anchors = node_obj.get("anchor")
    out: list[str] = []
    for a in _ensure_list(anchors):
        if isinstance(a, str) and a.strip():
            out.append(a)
    return out


def _build_graph(
    nodes: dict[str, dict[str, Any]],
    ref_fields: list[str],
) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {name: set() for name in nodes.keys()}
    for node_name, node_obj in nodes.items():
        if not isinstance(node_obj, dict):
            continue
        for field in ref_fields:
            for ref in _iter_refs_in_field(node_obj.get(field)):
                if ref.kind == "node" and ref.name:
                    graph.setdefault(node_name, set()).add(ref.name)
    return graph


def _reachable_from(starts: list[str], graph: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    stack: list[str] = [s for s in starts if s in graph]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        for nxt in graph.get(cur, set()):
            if nxt not in seen:
                stack.append(nxt)
    return seen


def _validate_ref_field_shape(value: Any) -> Optional[str]:
    """
    next/on_error/interrupt 的结构校验：
    - 允许 string / dict(NodeAttr) / list(mixed)
    - dict 形式必须包含 string 类型的 name
    """
    if value is None:
        return None
    if isinstance(value, str):
        return None
    if isinstance(value, dict):
        if not isinstance(value.get("name"), str) or not value.get("name"):
            return "引用对象必须包含非空字符串字段 name（例如 {\"name\": \"节点名\"}）"
        return None
    if isinstance(value, list):
        for idx, it in enumerate(value):
            msg = _validate_ref_field_shape(it)
            if msg is not None:
                return f"数组第 {idx} 项非法：{msg}"
        return None
    return f"不支持的类型：{type(value).__name__}（仅支持 string / object / array）"


def main(argv: list[str]) -> int:
    # 让输出尽量以 UTF-8 打印，避免在某些环境中中文变成乱码（例如默认 GBK）。
    if hasattr(sys.stdout, "reconfigure"):
        try:
            if (sys.stdout.encoding or "").lower() not in ("utf-8", "utf8"):
                sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description=(
            "快速检测 pipeline 资源：悬空节点/锚点引用、重复节点名、模板图片缺失等。\n"
            "常见用途：你改了 pipeline 文件后，启动时出现 Loading.Failed / invalid node id。"
        )
    )
    parser.add_argument(
        "--pipeline-dir",
        default="assets/resource/pipeline",
        help="pipeline 目录（默认：assets/resource/pipeline）",
    )
    parser.add_argument(
        "--image-dir",
        default="assets/resource/image",
        help="图片资源目录（默认：assets/resource/image）",
    )
    parser.add_argument(
        "--interface",
        default="assets/interface.json",
        help="interface.json（JSONC）路径，用于检查任务入口节点（默认：assets/interface.json）",
    )
    parser.add_argument(
        "--no-interface",
        action="store_true",
        help="不读取 interface.json（只检查 pipeline 内部）",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="严格模式：将 WARN 也视为失败（返回非 0）",
    )
    parser.add_argument(
        "--no-unreachable",
        action="store_true",
        help="不提示“可能未被任何任务入口触达”的节点（默认会提示为 WARN）",
    )
    args = parser.parse_args(argv)

    pipeline_dir = Path(args.pipeline_dir)
    image_dir = Path(args.image_dir)
    interface_path = Path(args.interface)

    issues: list[Issue] = []

    if not pipeline_dir.exists():
        issues.append(Issue(level="ERROR", code="PIPELINE_DIR_NOT_FOUND", message="pipeline 目录不存在", file=pipeline_dir))
        for i in issues:
            print(i.format_one_line())
        return 2

    pipeline_files = sorted([p for p in pipeline_dir.glob("*.json") if p.is_file()])
    if not pipeline_files:
        issues.append(Issue(level="ERROR", code="PIPELINE_EMPTY", message="pipeline 目录下没有任何 .json 文件", file=pipeline_dir))
        for i in issues:
            print(i.format_one_line())
        return 2

    # 1) 读取所有 pipeline 文件，收集节点定义
    node_to_files: dict[str, list[Path]] = {}
    all_nodes: dict[str, dict[str, Any]] = {}  # 节点名 -> 节点对象（若重复，仅保留第一个用于后续检查）
    all_anchors: set[str] = set()

    for pf in pipeline_files:
        obj, dup_keys, err = _load_json_file(pf)
        if err is not None:
            issues.append(Issue(level="ERROR", code="PIPELINE_JSON_INVALID", message=err, file=pf))
            continue
        if dup_keys:
            uniq = ", ".join(sorted(set(dup_keys)))
            issues.append(Issue(level="ERROR", code="DUPLICATE_JSON_KEY", message=f"文件内存在重复 key：{uniq}", file=pf))

        if not isinstance(obj, dict):
            issues.append(Issue(level="ERROR", code="PIPELINE_ROOT_NOT_OBJECT", message="顶层必须是 JSON Object（节点名 -> 节点对象）", file=pf))
            continue

        for k, v in obj.items():
            # 忽略编辑器/工具的元数据键
            if isinstance(k, str) and k.startswith("$"):
                continue
            if not isinstance(k, str) or not k.strip():
                issues.append(Issue(level="ERROR", code="INVALID_NODE_NAME", message="节点名必须是非空字符串", file=pf))
                continue

            node_to_files.setdefault(k, []).append(pf)
            if not isinstance(v, dict):
                issues.append(
                    Issue(
                        level="ERROR",
                        code="NODE_NOT_OBJECT",
                        message=f"节点内容必须是 JSON Object，当前类型为 {type(v).__name__}",
                        file=pf,
                        node=k,
                    )
                )
                if k not in all_nodes:
                    all_nodes[k] = {"__invalid_node_value__": v}
                continue

            if k not in all_nodes:
                all_nodes[k] = v

            # 收集锚点定义（用于检查 [Anchor] 引用）
            for a in _collect_anchor_definitions(v):
                all_anchors.add(a)

    # 2) 重复节点名（跨文件）检查
    for node_name, files in sorted(node_to_files.items(), key=lambda x: x[0]):
        if len(files) > 1:
            file_list = ", ".join(f.as_posix() for f in files)
            issues.append(
                Issue(
                    level="ERROR",
                    code="DUPLICATE_NODE_NAME",
                    message=f"节点名在多个文件中重复定义：{file_list}",
                    node=node_name,
                )
            )

    # 3) 引用检查（next/on_error + 兼容旧 interrupt）
    ref_fields = ["next", "on_error", "interrupt"]
    node_set = set(all_nodes.keys())
    for node_name, node_obj in all_nodes.items():
        if not isinstance(node_obj, dict):
            continue

        for field in ref_fields:
            if field not in node_obj:
                continue
            value = node_obj.get(field)
            shape_err = _validate_ref_field_shape(value)
            if shape_err is not None:
                issues.append(
                    Issue(
                        level="ERROR",
                        code="INVALID_REF_SHAPE",
                        message=shape_err,
                        node=node_name,
                        field=field,
                    )
                )
            for ref in _iter_refs_in_field(value):
                if not isinstance(ref.name, str) or not ref.name.strip():
                    issues.append(
                        Issue(
                            level="ERROR",
                            code="INVALID_REF",
                            message="引用项解析后为空（可能是 [] 前缀写法不正确）",
                            node=node_name,
                            field=field,
                        )
                    )
                    continue

                if ref.kind == "node":
                    if ref.name not in node_set:
                        issues.append(
                            Issue(
                                level="ERROR",
                                code="DANGLING_NODE_REF",
                                message=f"引用了不存在的节点：{ref.name}",
                                node=node_name,
                                field=field,
                            )
                        )
                else:
                    if ref.name not in all_anchors:
                        issues.append(
                            Issue(
                                level="ERROR",
                                code="DANGLING_ANCHOR_REF",
                                message=f"引用了不存在的锚点：{ref.name}",
                                node=node_name,
                                field=field,
                            )
                        )

    # 4) 模板资源检查（缺图是另一类常见“加载失败/运行失败”原因）
    if image_dir.exists():
        for node_name, node_obj in all_nodes.items():
            for tpl in _collect_templates_from_node(node_obj):
                tpl_path = image_dir / Path(tpl)
                if not tpl_path.exists():
                    issues.append(
                        Issue(
                            level="WARN",
                            code="MISSING_TEMPLATE",
                            message=f"模板图片不存在：{tpl}（期望路径：{tpl_path.as_posix()}）",
                            node=node_name,
                            field="recognition.param.template",
                        )
                    )
    else:
        issues.append(Issue(level="WARN", code="IMAGE_DIR_NOT_FOUND", message="图片目录不存在，跳过模板图片检查", file=image_dir))

    # 5) interface.json 入口检查（常见报错：invalid node id）
    task_entries: list[str] = []
    pipeline_override_keys: set[str] = set()
    if not args.no_interface and interface_path.exists():
        interface_obj, err = _load_jsonc_file(interface_path)
        if err is not None:
            issues.append(Issue(level="WARN", code="INTERFACE_PARSE_FAILED", message=err, file=interface_path))
        elif isinstance(interface_obj, dict):
            tasks = interface_obj.get("task")
            if isinstance(tasks, list):
                for t in tasks:
                    if isinstance(t, dict) and isinstance(t.get("entry"), str):
                        task_entries.append(t["entry"])

            def collect_pipeline_override(obj: Any) -> None:
                if isinstance(obj, dict):
                    po = obj.get("pipeline_override")
                    if isinstance(po, dict):
                        for k in po.keys():
                            if isinstance(k, str):
                                pipeline_override_keys.add(k)
                    for v in obj.values():
                        collect_pipeline_override(v)
                elif isinstance(obj, list):
                    for it in obj:
                        collect_pipeline_override(it)

            collect_pipeline_override(interface_obj)

            for entry in task_entries:
                if entry not in node_set:
                    issues.append(
                        Issue(
                            level="ERROR",
                            code="TASK_ENTRY_MISSING",
                            message=f"任务入口 entry 指向不存在的节点：{entry}",
                            file=interface_path,
                        )
                    )

            for k in sorted(pipeline_override_keys):
                if k not in node_set:
                    issues.append(
                        Issue(
                            level="WARN",
                            code="PIPELINE_OVERRIDE_UNKNOWN",
                            message=f"pipeline_override 里出现未知节点名（可能是拼写错误或节点已删除）：{k}",
                            file=interface_path,
                        )
                    )

    # 6) 可选：提示“可能未被任何入口触达”的节点（通常是遗留垃圾节点）
    if not args.no_unreachable and task_entries:
        graph = _build_graph(all_nodes, ref_fields=["next", "on_error"])
        reachable = _reachable_from(task_entries, graph)
        unreachable = sorted([n for n in node_set if n not in reachable])
        for n in unreachable:
            issues.append(
                Issue(
                    level="WARN",
                    code="UNREACHABLE_NODE",
                    message="该节点可能未被任何任务入口触达（可忽略，但常见于忘记删的节点）",
                    node=n,
                )
            )

    # 输出
    errors = [i for i in issues if i.level == "ERROR"]
    warns = [i for i in issues if i.level == "WARN"]

    for i in issues:
        print(i.format_one_line())

    print(
        f"\n检查完成：pipeline 文件 {len(pipeline_files)} 个，节点 {len(node_set)} 个，"
        f"锚点 {len(all_anchors)} 个，ERROR {len(errors)}，WARN {len(warns)}"
    )

    if errors:
        return 1
    if args.strict and warns:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
