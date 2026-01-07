# MSA 后台点击 Hook 方案规划书 v2

> 版本：2.2
> 日期：2026-01-06
> 状态：已完成

---

## 一、方案概述

通过 Proxy DLL 替换 MAA Framework 的 `MaaWin32ControlUnit.dll`，在用户选择 `SendMessage` 输入方式时，使用自定义控制单元实现后台点击。

---

## 二、技术方案

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      MSA 后台点击架构 v2                     │
├─────────────────────────────────────────────────────────────┤
│  Proxy DLL (MaaWin32ControlUnit.dll)                        │
│    - 加载原版 DLL (MaaWin32ControlUnit_original.dll)        │
│    - SendMessage 模式：返回自定义控制单元                   │
│    - 其他模式：透传原版控制单元                             │
├─────────────────────────────────────────────────────────────┤
│  自定义控制单元                                              │
│    - 截图：委托给原版控制单元                               │
│    - 输入：注入 Hook DLL → 写入共享内存 → 发送消息          │
├─────────────────────────────────────────────────────────────┤
│  Hook DLL (msa_hook.dll) - 注入到游戏进程                   │
│    - Hook GetCursorPos → 返回共享内存中的坐标               │
├─────────────────────────────────────────────────────────────┤
│  共享内存 - 自定义控制单元与 Hook DLL 的通信桥梁            │
│    - 目标坐标、窗口句柄、启用标志                           │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Proxy DLL

**技术约束**：

`MaaWin32ControlUnitHandle` 实际是 C++ 类指针（`Win32ControlUnitAPI*`），自定义控制单元必须继承该类并保持 ABI 兼容：

- 编译器：MSVC 2022（与 MAA Framework 一致）
- 接口涉及 `cv::Mat`、`std::string` 等 C++ 类型

**导出函数**：

| 函数 | 行为 |
|------|------|
| `MaaWin32ControlUnitGetVersion` | 透传原版 |
| `MaaWin32ControlUnitCreate` | 见下方逻辑 |
| `MaaWin32ControlUnitDestroy` | 清理资源 |

**Create 逻辑**：

```
MaaWin32ControlUnitCreate(hWnd, screencap, mouse, keyboard):
    加载原版 DLL
    调用原版 Create 获取原版控制单元

    if mouse == SendMessage:
        创建自定义控制单元包装器
        包装器.截图 = 原版控制单元
        包装器.输入 = 自定义实现
        return 包装器
    else:
        return 原版控制单元
```

### 2.3 自定义控制单元

自定义控制单元需实现 `Win32ControlUnitAPI` 的所有虚函数：

| 方法 | 实现方式 |
|------|---------|
| `connect()` | 委托原版 + 初始化注入 |
| `request_uuid(std::string&)` | 委托原版 |
| `get_features()` | 委托原版 |
| `screencap(cv::Mat&)` | 委托原版 |
| `click(int, int)` | 自定义 |
| `swipe(...)` | 自定义 |
| `touch_down/move/up(...)` | 自定义 |
| `click_key(int)` | 委托原版 |
| `input_text(const std::string&)` | 委托原版 |
| `key_down/up(int)` | 委托原版 |
| `scroll(int, int)` | 委托原版 |

**点击流程**：

1. 检查注入状态，失效则重新注入
2. 写入坐标到共享内存
3. 设置 `enabled = true`
4. 发送 `WM_ACTIVATE` 伪造激活
5. 发送 `WM_LBUTTONDOWN` / `WM_LBUTTONUP`
6. 设置 `enabled = false`

### 2.4 Hook DLL

**Hook 目标**：

| API | 作用 |
|-----|------|
| `GetCursorPos` | 返回共享内存中的目标坐标（需做客户区→屏幕坐标转换） |

**坐标转换**：

`GetCursorPos` Hook 负责将共享内存中的客户区坐标转换为屏幕坐标：

- 读取共享内存中的 `(target_x, target_y)` 客户区坐标
- 使用 `ClientToScreen(game_hwnd, &point)` 转换为屏幕坐标
- 返回转换后的屏幕坐标

**技术选型**：

- 注入方式：`CreateRemoteThread` + `LoadLibraryW`
- Hook 库：MinHook

### 2.5 通信机制

自定义控制单元与 Hook DLL 通过命名共享内存通信：

| 字段 | 类型 | 说明 |
|------|------|------|
| enabled | bool | Hook 是否生效 |
| target_x | int | 目标 X 坐标（客户区） |
| target_y | int | 目标 Y 坐标（客户区） |
| game_hwnd | HWND | 游戏窗口句柄 |
| injected_pid | DWORD | 被注入进程的 PID，用于检测进程是否存活 |
| version | DWORD | 协议版本 |

**Hook 行为**：

`enabled` 标志控制 `GetCursorPos` Hook 的行为：

| enabled | GetCursorPos |
|---------|--------------|
| true | 返回 `(target_x, target_y)` 转换后的屏幕坐标 |
| false | 透传原始 API，返回真实鼠标位置 |

---

## 三、用户操作流程

1. 启动游戏 → 启动 MSA
2. 选择"桌面端"控制器
3. 鼠标控制方式选择 `SendMessage`（后台模式）
4. 点击开始 → 自动注入 → 执行任务
5. 若后台模式不生效，用户可切换到 `SendMessageWithCursorPos`（前台模式）

---

## 四、项目结构

```
MSA/
├── hook/                            # 后台点击模块
│   ├── CMakeLists.txt
│   │
│   ├── proxy/                       # Proxy DLL
│   │   ├── dllmain.cpp              # DLL 入口，加载原版 DLL
│   │   ├── exports.cpp              # 导出函数实现
│   │   ├── control_unit.cpp         # 自定义控制单元实现
│   │   ├── control_unit.h
│   │   ├── injector.cpp             # 注入逻辑
│   │   └── shared_memory.cpp        # 共享内存（控制单元端）
│   │
│   ├── dll/                         # Hook DLL（已完成）
│   │   ├── dllmain.cpp
│   │   ├── hooks.cpp
│   │   └── shared_memory.cpp
│   │
│   ├── common/
│   │   └── protocol.h               # 共享内存结构定义
│   │
│   └── third_party/
│       └── minhook/
│
└── tools/
    └── install.py                   # 修改：打包时处理 DLL 替换
```

**构建产物**：

- `MaaWin32ControlUnit.dll` - Proxy DLL
- `MaaWin32ControlUnit_original.dll` - 原版 DLL（改名）
- `msa_hook.dll` - Hook DLL

---

## 五、开发阶段

### 阶段一：Hook DLL（已完成）

复用 v1 方案。

### 阶段二：分析 MAA 控制单元接口（已完成,见 <阶段二分析结果-MAA控制单元接口>）

- 分析导出函数签名和控制单元内部接口
- **验收**：明确需要实现的接口列表

### 阶段三：Proxy DLL 框架 + 截图 + 打包

- 实现 DLL 加载和导出函数转发
- 实现自定义控制单元框架，截图委托原版
- 更新 CMakeLists.txt 和 install.py
- **验收**：构建打包后，GUI 截图功能正常

### 阶段四：自定义输入实现

- 实现点击/触摸输入
- 集成注入逻辑和共享内存通信
- **验收**：构建打包后，GUI 后台点击生效

---

## 六、错误处理

| 错误场景 | 处理方式 |
|---------|---------|
| 原版 DLL 加载失败 | 记录日志，返回失败 |
| 游戏未启动 | 注入失败，返回失败 |
| 注入失败 | 记录日志，返回失败 |
| 共享内存失败 | 记录日志，返回失败 |

**原则**：失败不自动降级，用户可自行切换到 `SendMessageWithCursorPos`。

---

## 七、风险与注意事项

| 风险 | 缓解措施 |
|------|---------|
| 杀软误报 | 使用标准 API，代码开源 |
| MAA 更新导致接口变化 | 定期检查上游更新 |
| 多开场景 | 默认注入第一个进程 |
| C++ ABI 不兼容 | 使用 MSVC 编译，与 MAA Framework 保持一致 |

---

## 八、构建依赖

| 依赖 | 来源 |
|------|------|
| MAA Framework 头文件 | `source/include/ControlUnit/ControlUnitAPI.h` |
| OpenCV | MAA Framework 使用的版本 |
| MinHook | 已集成 |
