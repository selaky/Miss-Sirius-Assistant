# MSA 后台点击 Hook 方案规划书

> 版本：1.1
> 日期：2026-01-05
> 状态：待实施

---

## 一、项目背景与目标

### 1.1 现状

MSA 当前使用 MAA Framework 内置的 `Seize` 模式，需要游戏窗口前台、会抢占鼠标。

### 1.2 目标

实现真正的后台点击：游戏可在后台运行，不抢占鼠标，用户可正常使用电脑。

### 1.3 技术原理

《星纪元》通过 `GetCursorPos` 和 `GetForegroundWindow` 验证点击。解决方案：DLL 注入 + API Hook，伪造鼠标位置和窗口状态。

---

## 二、技术方案

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      MSA 后台点击架构                        │
├─────────────────────────────────────────────────────────────┤
│  自定义控制器 (msa_controller.dll)                          │
│    - 实现 MaaCustomControllerCallbacks                      │
│    - 截图：Windows Graphics Capture API                     │
│    - 点击：写入共享内存 → 发送 WM_LBUTTONDOWN/UP            │
├─────────────────────────────────────────────────────────────┤
│  Hook DLL (msa_hook.dll) - 注入到游戏进程                   │
│    - Hook GetCursorPos → 返回共享内存中的坐标               │
│    - Hook GetForegroundWindow → 返回游戏窗口句柄            │
├─────────────────────────────────────────────────────────────┤
│  共享内存 - 控制器与 Hook DLL 的通信桥梁                    │
│    - 目标坐标、窗口句柄、启用标志                           │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 自定义控制器

使用 MAA Framework 的 `MaaCustomControllerCreate` API 创建自定义控制器，实现 `MaaCustomControllerCallbacks` 回调。

**需要实现的回调**：

| 回调 | 实现方式 |
|------|---------|
| `connect` | 初始化共享内存，返回成功 |
| `screencap` | 使用 Windows Graphics Capture API|
| `click` | 写入坐标到共享内存 → 发送窗口消息 |
| `touch_down/move/up` | 同上，支持更精细的控制 |
| 其他 | 按需实现或返回失败 |

**实现原则**：

- **参考 MAA 的实现方式**，使用相同的 Windows API 和设计模式
- 保持接口和行为与 MAA 一致，减少学习成本和兼容性问题

### 2.3 Hook DLL

**Hook 目标**：

| API | 作用 |
|-----|------|
| `GetCursorPos` | 返回共享内存中的目标坐标（需做客户区→屏幕坐标转换） |
| `GetForegroundWindow` | 返回游戏窗口句柄 |

**技术选型**：

- 注入方式：`CreateRemoteThread` + `LoadLibraryW`（标准方式，不影响其他进程，杀软友好）
- Hook 库：MinHook（轻量、稳定、BSD 协议）

### 2.4 通信机制

控制器与 Hook DLL 通过命名共享内存通信：

| 字段 | 类型 | 说明 |
|------|------|------|
| enabled | bool | Hook 是否生效 |
| target_x | int | 目标 X 坐标（客户区） |
| target_y | int | 目标 Y 坐标（客户区） |
| game_hwnd | HWND | 游戏窗口句柄 |
| version | DWORD | 协议版本 |

**点击流程**：

1. 控制器写入坐标，设置 enabled = true
2. 控制器发送 WM_LBUTTONDOWN
3. 游戏调用 GetCursorPos → Hook 返回伪造坐标
4. 游戏调用 GetForegroundWindow → Hook 返回游戏句柄
5. 游戏处理点击
6. 控制器发送 WM_LBUTTONUP，设置 enabled = false

---

## 三、与 MAA Framework 集成

### 3.1 控制器集成

自定义控制器编译为 DLL，通过 Python binding 或直接 C API 与 MAA 集成。在 GUI 中作为独立控制器选项供用户选择。

### 3.2 注入任务

新增任务 `启动后台操作`，位于任务列表最前面，默认勾选。执行时运行注入器将 Hook DLL 注入游戏进程。

```
任务列表：
☑ 启动后台操作    ← 新增
☑ 跑图
☐ 竞技场
```

### 3.3 用户操作流程

1. 启动游戏 → 启动 MSA
2. 选择"桌面端（后台版）"控制器
3. 确认勾选"启动后台操作"
4. 点击开始 → 自动注入 → 执行任务
5. 用户可切换到其他窗口正常使用

---

## 四、项目结构

```
MSA/
├── assets/
│   ├── interface.json              # 修改：添加新控制器和任务
│   └── resource/pipeline/
│       └── 启动后台操作.json       # 新增：注入任务
│
├── hook/                            # 新增：后台点击模块
│   ├── CMakeLists.txt
│   │
│   ├── controller/                 # 自定义控制器
│   │   ├── controller.cpp          # MaaCustomControllerCallbacks 实现
│   │   ├── screencap.cpp           # Windows Graphics Capture 截图
│   │   ├── input.cpp               # 点击/滑动实现
│   │   └── shared_memory.cpp       # 共享内存（控制器端）
│   │
│   ├── injector/                   # 注入器
│   │   └── main.cpp
│   │
│   ├── dll/                        # Hook DLL
│   │   ├── dllmain.cpp
│   │   ├── hooks.cpp               # GetCursorPos/GetForegroundWindow Hook
│   │   └── shared_memory.cpp       # 共享内存（DLL端）
│   │
│   ├── common/
│   │   └── protocol.h              # 共享内存结构定义
│   │
│   └── third_party/
│       └── minhook/
│
└── tools/
    └── install.py                  # 修改：打包时包含 hook 模块
```

**构建产物**：

- `msa_controller.dll` - 自定义控制器
- `msa_hook.dll` - Hook DLL
- `injector.exe` - 注入器

---

## 五、开发阶段

### 阶段一：Hook DLL

- MinHook 集成
- GetCursorPos / GetForegroundWindow Hook
- 共享内存通信
- 注入器
- **验收**：手动注入后，用测试程序发送消息能触发游戏点击

### 阶段二：自定义控制器

- MaaCustomControllerCallbacks 实现
- Windows Graphics Capture 截图
- 点击/触摸输入
- **验收**：通过 MAA API 调用控制器能完成截图和点击

### 阶段三：集成与测试

- interface.json 配置
- 注入任务 Pipeline
- 错误处理和日志
- 构建脚本更新
- **验收**：用户可在 GUI 中选择后台模式，完整执行任务

---

## 六、错误处理

| 错误场景 | 处理方式 |
|---------|---------|
| 游戏未启动 | 日志 + GUI 提示，引导用户先启动游戏 |
| 注入失败 | 日志 + GUI 提示，引导切换到原生控制器 |
| 共享内存失败 | 日志 + GUI 提示 |

**原则**：不自动回退，明确告知用户问题，避免困惑。

---

## 七、风险与注意事项

| 风险 | 缓解措施 |
|------|---------|
| 杀软误报 | 使用标准 API，代码开源，考虑签名 |
| 游戏更新 | Hook 的是 Windows API 而非游戏函数，兼容性好；保留原生控制器备选 |
| 多开场景 | 默认注入第一个进程，后续可扩展 |
| 权限问题 | 注入器 manifest 声明管理员权限 |

---

## 八、后续扩展

- 键盘 Hook（如果游戏增加键盘操作）
- 滑动操作支持
- 多开支持

---

## 九、参考资料

- [MAA Framework 自定义控制器](https://maafw.xyz/docs/2.2-IntegratedInterfaceOverview#maacustomcontrollercreate)
- [MaaCustomControllerCallbacks 定义](https://github.com/MaaXYZ/MaaFramework/blob/main/include/MaaFramework/Instance/MaaCustomController.h)
- [Windows Graphics Capture](https://docs.microsoft.com/en-us/windows/uwp/audio-video-camera/screen-capture)
- [MinHook](https://github.com/TsudaKageworker/minhook)

---

*本规划书为顶层设计文档，具体实现细节在各阶段开发时确定。*
