#!/usr/bin/env python3
"""
MAA Framework 兼容性检测工具

检测 MAA Framework 更新后是否与 MSA Hook 代理方案兼容。

使用方法:
    python my_tools/hook/check_maa_compat.py              # 执行兼容性检测
    python my_tools/hook/check_maa_compat.py --offline    # 离线模式（使用缓存的官方定义）
    python my_tools/hook/check_maa_compat.py --verbose    # 显示详细信息
    python my_tools/hook/check_maa_compat.py --json       # JSON 格式输出

工作原理:
    1. 从 MAA Framework GitHub 仓库获取最新的 ControlUnitAPI.h
    2. 解析官方的虚函数表定义
    3. 与本地 hook/proxy/control_unit.h 的实现对比
    4. 报告差异并提供修复建议
"""

import sys
import re
import json
import argparse
import hashlib
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

# 尝试导入网络库
try:
    import urllib.request
    import urllib.error
    HAS_URLLIB = True
except ImportError:
    HAS_URLLIB = False


# ========== 配置 ==========

SCRIPT_DIR = Path(__file__).parent
CACHE_DIR = SCRIPT_DIR / "maa_cache"
PROJECT_ROOT = SCRIPT_DIR.parent.parent

# MAA Framework 官方源码 URL
MAA_GITHUB_RAW = "https://raw.githubusercontent.com/MaaXYZ/MaaFramework/main"
OFFICIAL_API_URL = f"{MAA_GITHUB_RAW}/source/include/ControlUnit/ControlUnitAPI.h"

# 本地文件路径
LOCAL_PATHS = {
    "control_unit_h": "hook/proxy/control_unit.h",
    "maa_def_h": "deps/include/MaaFramework/MaaDef.h",
}

# 缓存文件
CACHE_FILES = {
    "official_api": CACHE_DIR / "official_ControlUnitAPI.h",
    "official_meta": CACHE_DIR / "official_meta.json",
}


# ========== 数据结构 ==========

@dataclass
class VirtualFunction:
    """虚函数定义"""
    index: int
    name: str
    signature: str
    return_type: str = ""
    params: str = ""
    is_const: bool = False
    is_destructor: bool = False

    def __eq__(self, other):
        if not isinstance(other, VirtualFunction):
            return False
        # 比较时忽略索引，只比较签名
        return self.name == other.name and self.signature == other.signature

    def signature_match(self, other: "VirtualFunction") -> bool:
        """检查签名是否匹配（忽略空格差异）"""
        def normalize(s):
            return re.sub(r'\s+', ' ', s).strip()
        return normalize(self.signature) == normalize(other.signature)


@dataclass
class VTableDiff:
    """虚函数表差异"""
    missing_in_local: list = field(default_factory=list)  # 官方有，本地没有
    extra_in_local: list = field(default_factory=list)    # 本地有，官方没有
    order_changed: list = field(default_factory=list)     # 顺序变化
    signature_changed: list = field(default_factory=list) # 签名变化

    @property
    def has_diff(self) -> bool:
        return bool(self.missing_in_local or self.extra_in_local or
                   self.order_changed or self.signature_changed)

    @property
    def is_abi_breaking(self) -> bool:
        """是否破坏 ABI 兼容性"""
        # 缺失函数、顺序变化都会破坏 ABI
        return bool(self.missing_in_local or self.order_changed)


@dataclass
class CompatReport:
    """兼容性报告"""
    compatible: bool
    official_vtable: list
    local_vtable: list
    diff: VTableDiff
    official_source: str = ""
    local_source: str = ""
    fetch_time: str = ""
    error: str = ""


# ========== 网络获取 ==========

def fetch_official_api(use_cache: bool = False) -> tuple[str, str]:
    """
    从 GitHub 获取官方 ControlUnitAPI.h

    Returns:
        (content, source_info) 文件内容和来源信息
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # 离线模式或网络不可用时使用缓存
    if use_cache:
        if CACHE_FILES["official_api"].exists():
            content = CACHE_FILES["official_api"].read_text(encoding="utf-8")
            meta = {}
            if CACHE_FILES["official_meta"].exists():
                meta = json.loads(CACHE_FILES["official_meta"].read_text(encoding="utf-8"))
            return content, f"缓存 ({meta.get('fetch_time', '未知时间')})"
        else:
            raise RuntimeError("离线模式但缓存不存在，请先联网运行一次")

    if not HAS_URLLIB:
        raise RuntimeError("urllib 不可用")

    # 从 GitHub 获取
    try:
        req = urllib.request.Request(
            OFFICIAL_API_URL,
            headers={"User-Agent": "MSA-CompatChecker/1.0"}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read().decode("utf-8")

        # 保存缓存
        CACHE_FILES["official_api"].write_text(content, encoding="utf-8")
        meta = {
            "url": OFFICIAL_API_URL,
            "fetch_time": datetime.now().isoformat(),
            "sha256": hashlib.sha256(content.encode()).hexdigest()[:16],
        }
        CACHE_FILES["official_meta"].write_text(
            json.dumps(meta, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        return content, f"GitHub ({meta['fetch_time'][:10]})"

    except urllib.error.URLError as e:
        # 网络错误，尝试使用缓存
        if CACHE_FILES["official_api"].exists():
            content = CACHE_FILES["official_api"].read_text(encoding="utf-8")
            return content, f"缓存 (网络错误: {e.reason})"
        raise RuntimeError(f"无法获取官方定义: {e.reason}")


def read_local_api() -> tuple[str, str]:
    """
    读取本地 control_unit.h

    Returns:
        (content, path) 文件内容和路径
    """
    path = PROJECT_ROOT / LOCAL_PATHS["control_unit_h"]
    if not path.exists():
        raise RuntimeError(f"本地文件不存在: {path}")

    content = path.read_text(encoding="utf-8")
    return content, str(path.relative_to(PROJECT_ROOT))


# ========== 解析逻辑 ==========

def parse_vtable(content: str, class_name: str = "ControlUnitAPI") -> list[VirtualFunction]:
    """
    从 C++ 头文件中解析虚函数表

    Args:
        content: 头文件内容
        class_name: 要解析的类名

    Returns:
        虚函数列表（按声明顺序）
    """
    vtable = []

    # 提取类体
    # 匹配 class ClassName { ... }; 或 class ClassName : public Base { ... };
    class_pattern = rf"class\s+{class_name}\s*(?::\s*public\s+\w+)?\s*\{{([^}}]+(?:\{{[^}}]*\}}[^}}]*)*)\}}"
    class_match = re.search(class_pattern, content, re.DOTALL)

    if not class_match:
        return vtable

    class_body = class_match.group(1)

    # 解析虚函数
    # 匹配: virtual ReturnType name(params) [const] [= 0];
    virtual_pattern = r"virtual\s+(~?\w[\w\s\*&<>:]*?)\s*\(([^)]*)\)\s*(const)?\s*(?:=\s*(?:0|default))?\s*;"

    for match in re.finditer(virtual_pattern, class_body):
        full_match = match.group(0)
        name_and_return = match.group(1).strip()
        params = match.group(2).strip()
        is_const = match.group(3) is not None

        # 分离返回类型和函数名
        if name_and_return.startswith("~"):
            # 析构函数
            name = name_and_return
            return_type = ""
            is_destructor = True
        else:
            # 普通函数: "bool connect" -> return_type="bool", name="connect"
            parts = name_and_return.rsplit(None, 1)
            if len(parts) == 2:
                return_type, name = parts
            else:
                return_type = ""
                name = parts[0]
            is_destructor = False

        # 构建规范化签名
        signature = f"virtual {name_and_return}({params})"
        if is_const:
            signature += " const"

        vtable.append(VirtualFunction(
            index=len(vtable),
            name=name,
            signature=signature,
            return_type=return_type,
            params=params,
            is_const=is_const,
            is_destructor=is_destructor,
        ))

    return vtable


def compare_vtables(official: list[VirtualFunction],
                   local: list[VirtualFunction]) -> VTableDiff:
    """
    对比两个虚函数表

    Args:
        official: 官方定义的虚函数表
        local: 本地实现的虚函数表

    Returns:
        差异报告
    """
    diff = VTableDiff()

    official_names = {vf.name: vf for vf in official}
    local_names = {vf.name: vf for vf in local}

    # 检查缺失的函数（官方有，本地没有）
    for name, vf in official_names.items():
        if name not in local_names:
            diff.missing_in_local.append(vf)

    # 检查多余的函数（本地有，官方没有）
    for name, vf in local_names.items():
        if name not in official_names:
            diff.extra_in_local.append(vf)

    # 检查顺序和签名
    official_order = [(vf.name, vf.index) for vf in official]
    local_order = [(vf.name, vf.index) for vf in local]

    # 只比较两边都有的函数
    common_names = set(official_names.keys()) & set(local_names.keys())

    for name in common_names:
        off_vf = official_names[name]
        loc_vf = local_names[name]

        # 检查索引（顺序）
        if off_vf.index != loc_vf.index:
            diff.order_changed.append({
                "name": name,
                "official_index": off_vf.index,
                "local_index": loc_vf.index,
            })

        # 检查签名
        if not off_vf.signature_match(loc_vf):
            diff.signature_changed.append({
                "name": name,
                "official": off_vf.signature,
                "local": loc_vf.signature,
            })

    return diff


# ========== 报告生成 ==========

def format_report(report: CompatReport, verbose: bool = False) -> str:
    """格式化文本报告"""
    lines = []
    lines.append("=" * 70)
    lines.append("MAA Framework 兼容性检测报告")
    lines.append("=" * 70)

    if report.error:
        lines.append(f"\n[错误] {report.error}")
        return "\n".join(lines)

    # 来源信息
    lines.append(f"\n官方来源: {report.official_source}")
    lines.append(f"本地文件: {report.local_source}")
    if report.fetch_time:
        lines.append(f"检测时间: {report.fetch_time}")

    # 虚函数表概览
    lines.append(f"\n官方虚函数数量: {len(report.official_vtable)}")
    lines.append(f"本地虚函数数量: {len(report.local_vtable)}")

    # 详细虚函数列表（verbose 模式）
    if verbose:
        lines.append("\n--- 官方虚函数表 ---")
        for vf in report.official_vtable:
            lines.append(f"  [{vf.index:2d}] {vf.signature}")

        lines.append("\n--- 本地虚函数表 ---")
        for vf in report.local_vtable:
            lines.append(f"  [{vf.index:2d}] {vf.signature}")

    # 差异报告
    diff = report.diff
    lines.append("\n" + "-" * 70)

    if not diff.has_diff:
        lines.append("\n[OK] 虚函数表完全匹配，兼容性良好")
    else:
        if diff.missing_in_local:
            lines.append(f"\n[严重] 缺失 {len(diff.missing_in_local)} 个虚函数（官方新增，本地未实现）:")
            for vf in diff.missing_in_local:
                lines.append(f"  + [{vf.index:2d}] {vf.signature}")

        if diff.order_changed:
            lines.append(f"\n[严重] {len(diff.order_changed)} 个虚函数顺序变化（ABI 不兼容）:")
            for item in diff.order_changed:
                lines.append(f"  ! {item['name']}: 官方索引 {item['official_index']} -> 本地索引 {item['local_index']}")

        if diff.signature_changed:
            lines.append(f"\n[警告] {len(diff.signature_changed)} 个虚函数签名变化:")
            for item in diff.signature_changed:
                lines.append(f"  ~ {item['name']}:")
                lines.append(f"      官方: {item['official']}")
                lines.append(f"      本地: {item['local']}")

        if diff.extra_in_local:
            lines.append(f"\n[信息] 本地多出 {len(diff.extra_in_local)} 个虚函数（可能是旧版遗留）:")
            for vf in diff.extra_in_local:
                lines.append(f"  - [{vf.index:2d}] {vf.signature}")

    # 结论和建议
    lines.append("\n" + "=" * 70)

    if report.compatible:
        lines.append("结论: [兼容] Hook 代理方案应该可以正常工作")
    else:
        lines.append("结论: [不兼容] 需要更新 hook/proxy/control_unit.h")
        lines.append("")
        lines.append("修复步骤:")
        lines.append("  1. 对照上方差异，更新 hook/proxy/control_unit.h 中的 ControlUnitAPI 类")
        lines.append("  2. 确保虚函数顺序与官方完全一致（ABI 兼容的关键）")
        lines.append("  3. 更新 MsaControlUnit 类实现新增的虚函数")
        lines.append("  4. 重新编译 proxy DLL")
        lines.append("  5. 测试验证")
        lines.append("")
        lines.append("官方源码参考:")
        lines.append(f"  {OFFICIAL_API_URL}")

    return "\n".join(lines)


def format_json(report: CompatReport) -> str:
    """格式化 JSON 报告"""
    data = {
        "compatible": report.compatible,
        "official_source": report.official_source,
        "local_source": report.local_source,
        "fetch_time": report.fetch_time,
        "official_vtable": [
            {"index": vf.index, "name": vf.name, "signature": vf.signature}
            for vf in report.official_vtable
        ],
        "local_vtable": [
            {"index": vf.index, "name": vf.name, "signature": vf.signature}
            for vf in report.local_vtable
        ],
        "diff": {
            "has_diff": report.diff.has_diff,
            "is_abi_breaking": report.diff.is_abi_breaking,
            "missing_in_local": [
                {"index": vf.index, "name": vf.name, "signature": vf.signature}
                for vf in report.diff.missing_in_local
            ],
            "extra_in_local": [
                {"index": vf.index, "name": vf.name, "signature": vf.signature}
                for vf in report.diff.extra_in_local
            ],
            "order_changed": report.diff.order_changed,
            "signature_changed": report.diff.signature_changed,
        },
        "error": report.error,
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


# ========== 主函数 ==========

def check_compatibility(offline: bool = False) -> CompatReport:
    """执行兼容性检测"""
    report = CompatReport(
        compatible=True,
        official_vtable=[],
        local_vtable=[],
        diff=VTableDiff(),
        fetch_time=datetime.now().isoformat(),
    )

    try:
        # 获取官方定义
        official_content, official_source = fetch_official_api(use_cache=offline)
        report.official_source = official_source

        # 读取本地定义
        local_content, local_source = read_local_api()
        report.local_source = local_source

        # 解析虚函数表
        report.official_vtable = parse_vtable(official_content, "ControlUnitAPI")
        report.local_vtable = parse_vtable(local_content, "ControlUnitAPI")

        if not report.official_vtable:
            report.error = "无法从官方源码解析虚函数表"
            report.compatible = False
            return report

        if not report.local_vtable:
            report.error = "无法从本地文件解析虚函数表"
            report.compatible = False
            return report

        # 对比
        report.diff = compare_vtables(report.official_vtable, report.local_vtable)

        # 判断兼容性
        report.compatible = not report.diff.is_abi_breaking

    except Exception as e:
        report.error = str(e)
        report.compatible = False

    return report


def main():
    parser = argparse.ArgumentParser(
        description="MAA Framework 兼容性检测工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s              # 从 GitHub 获取最新定义并检测
  %(prog)s --offline    # 使用缓存的官方定义（离线模式）
  %(prog)s --verbose    # 显示详细的虚函数表
  %(prog)s --json       # JSON 格式输出

工作原理:
  1. 从 MAA Framework GitHub 获取最新的 ControlUnitAPI.h
  2. 与本地 hook/proxy/control_unit.h 对比虚函数表
  3. 报告差异，判断是否需要适配

官方源码:
  https://github.com/MaaXYZ/MaaFramework
        """
    )

    parser.add_argument("--offline", action="store_true",
                        help="离线模式，使用缓存的官方定义")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="显示详细信息")
    parser.add_argument("-j", "--json", action="store_true",
                        help="JSON 格式输出")

    args = parser.parse_args()

    # 执行检测
    report = check_compatibility(offline=args.offline)

    # 输出
    if args.json:
        print(format_json(report))
    else:
        print(format_report(report, args.verbose))

    # 返回码: 0=兼容, 1=不兼容, 2=错误
    if report.error:
        sys.exit(2)
    elif report.compatible:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
