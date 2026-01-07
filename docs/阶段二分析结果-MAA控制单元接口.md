# 阶段二分析结果：MAA 控制单元接口

## 1. DLL 导出函数

`MaaWin32ControlUnit.dll` 导出 3 个 C 函数：

| 函数 | 签名 | 说明 |
|------|------|------|
| `MaaWin32ControlUnitGetVersion` | `const char*()` | 返回 MAA_VERSION 字符串 |
| `MaaWin32ControlUnitCreate` | `MaaWin32ControlUnitHandle(void* hWnd, MaaWin32ScreencapMethod, MaaWin32InputMethod mouse, MaaWin32InputMethod keyboard)` | 创建控制单元 |
| `MaaWin32ControlUnitDestroy` | `void(MaaWin32ControlUnitHandle)` | 销毁控制单元 |

## 2. 类型定义

```cpp
// Handle 实际是 C++ 类指针
using MaaWin32ControlUnitHandle = MAA_NS::CtrlUnitNs::Win32ControlUnitAPI*;

// 输入方式枚举（位掩码，但实际只选一个）
typedef uint64_t MaaWin32InputMethod;
#define MaaWin32InputMethod_None 0ULL
#define MaaWin32InputMethod_Seize 1ULL
#define MaaWin32InputMethod_SendMessage (1ULL << 1)        // = 2
#define MaaWin32InputMethod_PostMessage (1ULL << 2)        // = 4
#define MaaWin32InputMethod_LegacyEvent (1ULL << 3)        // = 8
#define MaaWin32InputMethod_PostThreadMessage (1ULL << 4)  // = 16
#define MaaWin32InputMethod_SendMessageWithCursorPos (1ULL << 5)  // = 32
#define MaaWin32InputMethod_PostMessageWithCursorPos (1ULL << 6)  // = 64

// 截图方式枚举
typedef uint64_t MaaWin32ScreencapMethod;
#define MaaWin32ScreencapMethod_None 0ULL
#define MaaWin32ScreencapMethod_GDI 1ULL
#define MaaWin32ScreencapMethod_FramePool (1ULL << 1)
#define MaaWin32ScreencapMethod_DXGI_DesktopDup (1ULL << 2)
#define MaaWin32ScreencapMethod_DXGI_DesktopDup_Window (1ULL << 3)
#define MaaWin32ScreencapMethod_PrintWindow (1ULL << 4)
#define MaaWin32ScreencapMethod_ScreenDC (1ULL << 5)

// 控制器特性标志
typedef uint64_t MaaControllerFeature;
#define MaaControllerFeature_None 0
#define MaaControllerFeature_UseMouseDownAndUpInsteadOfClick 1ULL
#define MaaControllerFeature_UseKeyboardDownAndUpInsteadOfClick (1ULL << 1)
```

## 3. 类继承关系

```
ControlUnitAPI (纯虚基类)
    └── Win32ControlUnitAPI (空派生，仅析构函数)
            └── Win32ControlUnitMgr (实际实现)
```

## 4. 需实现的虚函数

`ControlUnitAPI` 定义的纯虚函数（全部需要实现）：

| 方法 | 签名 | Proxy 实现方式 |
|------|------|---------------|
| `connect` | `bool()` | 委托原版 + 初始化注入 |
| `request_uuid` | `bool(std::string& uuid)` | 委托原版 |
| `get_features` | `MaaControllerFeature() const` | 委托原版 |
| `start_app` | `bool(const std::string& intent)` | 委托原版 |
| `stop_app` | `bool(const std::string& intent)` | 委托原版 |
| `screencap` | `bool(cv::Mat& image)` | 委托原版 |
| `click` | `bool(int x, int y)` | **自定义** |
| `swipe` | `bool(int x1, int y1, int x2, int y2, int duration)` | **自定义** |
| `touch_down` | `bool(int contact, int x, int y, int pressure)` | **自定义** |
| `touch_move` | `bool(int contact, int x, int y, int pressure)` | **自定义** |
| `touch_up` | `bool(int contact)` | **自定义** |
| `click_key` | `bool(int key)` | 委托原版 |
| `input_text` | `bool(const std::string& text)` | 委托原版 |
| `key_down` | `bool(int key)` | 委托原版 |
| `key_up` | `bool(int key)` | 委托原版 |
| `scroll` | `bool(int dx, int dy)` | 委托原版 |

## 5. 依赖项

### 5.1 头文件依赖

```cpp
#include <string>
#include <chrono>
#include "MaaFramework/MaaDef.h"      // 类型定义
#include "MaaUtils/NoWarningCVMat.hpp" // cv::Mat
```

### 5.2 编译依赖

| 依赖 | 说明 |
|------|------|
| MSVC 2022 | 与 MAA Framework 保持 ABI 兼容 |
| OpenCV | `cv::Mat` 类型，需与 MAA 使用的版本一致 |
| C++17 | `std::string`、`std::filesystem` 等 |

## 6. Proxy DLL 实现要点

### 6.1 Create 逻辑

```cpp
MaaWin32ControlUnitHandle MaaWin32ControlUnitCreate(
    void* hWnd,
    MaaWin32ScreencapMethod screencap_method,
    MaaWin32InputMethod mouse_method,
    MaaWin32InputMethod keyboard_method)
{
    // 1. 加载原版 DLL
    // 2. 调用原版 Create 获取原版控制单元
    // 3. 判断 mouse_method
    if (mouse_method == MaaWin32InputMethod_SendMessage) {
        // 创建自定义控制单元包装器
        // 包装器持有原版控制单元指针
        return new MsaControlUnit(original_unit, hWnd);
    }
    // 4. 其他模式直接返回原版
    return original_unit;
}
```

### 6.2 自定义控制单元类设计

```cpp
class MsaControlUnit : public Win32ControlUnitAPI {
public:
    MsaControlUnit(Win32ControlUnitAPI* original, HWND hwnd);
    ~MsaControlUnit() override;

    // 委托给原版
    bool connect() override;
    bool request_uuid(std::string& uuid) override;
    MaaControllerFeature get_features() const override;
    bool start_app(const std::string& intent) override;
    bool stop_app(const std::string& intent) override;
    bool screencap(cv::Mat& image) override;
    bool click_key(int key) override;
    bool input_text(const std::string& text) override;
    bool key_down(int key) override;
    bool key_up(int key) override;
    bool scroll(int dx, int dy) override;

    // 自定义实现
    bool click(int x, int y) override;
    bool swipe(int x1, int y1, int x2, int y2, int duration) override;
    bool touch_down(int contact, int x, int y, int pressure) override;
    bool touch_move(int contact, int x, int y, int pressure) override;
    bool touch_up(int contact) override;

private:
    Win32ControlUnitAPI* original_;  // 原版控制单元
    HWND hwnd_;                      // 游戏窗口句柄
    bool injected_ = false;          // 注入状态
};
```

## 7. 已完成组件

### 7.1 共享内存协议 (`hook/common/protocol.h`)

```cpp
typedef struct _MSA_SHARED_DATA {
    DWORD version;      // 协议版本 (=1)
    BOOL enabled;       // Hook 是否生效
    int target_x;       // 目标 X 坐标（客户区）
    int target_y;       // 目标 Y 坐标（客户区）
    HWND game_hwnd;     // 游戏窗口句柄
    DWORD injected_pid; // 被注入进程 PID
    BYTE reserved[32];  // 保留字段
} MSA_SHARED_DATA;

#define MSA_SHARED_MEMORY_NAME L"Local\\MSA_BackgroundClick_SharedMemory"
#define MSA_PROTOCOL_VERSION 1
```

### 7.2 Hook DLL (`hook/dll/`)

- `hooks.cpp`: GetCursorPos Hook，读取共享内存坐标并转换为屏幕坐标
- `shared_memory.cpp`: 打开并映射共享内存（DLL 端）
- 使用 MinHook 库
