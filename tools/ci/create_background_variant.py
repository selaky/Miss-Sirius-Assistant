"""后台版转换脚本

将已完成的原版 install/ 目录复制为 install-bg/，
注入 Hook 模块并修改 controller 配置，生成后台版产物。
"""

import argparse
import json
import shutil
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="创建后台版产物")
    parser.add_argument(
        "--hook-dir",
        required=True,
        help="Hook 构建产物目录（包含 msa_hook.dll 和 MaaWin32ControlUnit.dll）",
    )
    parser.add_argument(
        "--icon",
        required=True,
        help="后台版图标文件路径（.ico）",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    working_dir = Path(__file__).parent.parent.parent
    install_path = working_dir / "install"
    bg_path = working_dir / "install-bg"
    hook_dir = Path(args.hook_dir)
    icon_path = Path(args.icon)

    # 1. 复制 install/ 为 install-bg/
    if bg_path.exists():
        shutil.rmtree(bg_path)
    shutil.copytree(install_path, bg_path)
    print(f"复制 {install_path} -> {bg_path}")

    # 2. 注入 Hook DLL 到 runtimes/win-x64/native/
    native_dir = bg_path / "runtimes" / "win-x64" / "native"
    if not native_dir.exists():
        raise FileNotFoundError(f"native 目录不存在: {native_dir}")

    original_dll = native_dir / "MaaWin32ControlUnit.dll"
    renamed_dll = native_dir / "MaaWin32ControlUnit_original.dll"

    if original_dll.exists():
        original_dll.rename(renamed_dll)
        print(f"重命名 {original_dll.name} -> {renamed_dll.name}")
    else:
        print(f"警告: {original_dll} 不存在，跳过重命名")

    # 复制代理 MaaWin32ControlUnit.dll（Hook 构建产物）
    proxy_dll = hook_dir / "MaaWin32ControlUnit.dll"
    shutil.copy2(proxy_dll, native_dir / "MaaWin32ControlUnit.dll")
    print(f"复制代理 DLL: {proxy_dll} -> {native_dir}")

    # 复制 msa_hook.dll
    hook_dll = hook_dir / "msa_hook.dll"
    shutil.copy2(hook_dll, native_dir / "msa_hook.dll")
    print(f"复制 Hook DLL: {hook_dll} -> {native_dir}")

    # 3. 修改 interface.json 中的 controller 配置
    interface_file = bg_path / "interface.json"
    with open(interface_file, "r", encoding="utf-8") as f:
        interface = json.load(f)

    for controller in interface.get("controller", []):
        if controller.get("type") == "Win32" and "win32" in controller:
            controller["win32"]["mouse"] = "SendMessage"
            controller["win32"]["keyboard"] = "SendMessage"

    with open(interface_file, "w", encoding="utf-8") as f:
        json.dump(interface, f, ensure_ascii=False, indent=4)
    print("已修改后台版 interface.json controller 配置")

    # 4. 替换图标
    assets_dir = bg_path / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(icon_path, assets_dir / "logo.ico")
    print(f"已替换后台版图标: {icon_path} -> {assets_dir / 'logo.ico'}")

    print("后台版创建完成！")


if __name__ == "__main__":
    main()
