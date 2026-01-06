/**
 * MSA 自定义控制器 - MaaCustomControllerCallbacks 实现
 */

#include "controller.h"
#include "shared_memory.h"
#include "screencap.h"
#include "injector.h"
#include "../common/protocol.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <tlhelp32.h>

// 游戏进程名
#define GAME_PROCESS_NAME L"StarEra.exe"
// 游戏窗口类名
#define GAME_WINDOW_CLASS L"UnityWndClass"

// 日志宏
#define LOG(fmt, ...) printf("[MSA Controller] " fmt "\n", ##__VA_ARGS__)
#define LOG_ERROR(fmt, ...) printf("[MSA Controller Error] " fmt " (错误码: %lu)\n", ##__VA_ARGS__, GetLastError())

// 控制器上下文
struct MsaControllerContext {
    HWND hwnd;                          // 游戏窗口句柄
    DWORD pid;                          // 游戏进程 PID
    ScreencapContext* screencapCtx;     // 截图器上下文
    InjectorContext* injectorCtx;       // 注入器上下文
    MaaCustomControllerCallbacks callbacks;  // 回调结构
    char uuid[64];                      // UUID 字符串
    bool connected;                     // 是否已连接
};

// ==================== 辅助函数 ====================

// 查找游戏进程
static DWORD FindGameProcess() {
    HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnapshot == INVALID_HANDLE_VALUE) {
        return 0;
    }

    PROCESSENTRY32W pe32;
    pe32.dwSize = sizeof(pe32);

    DWORD pid = 0;
    if (Process32FirstW(hSnapshot, &pe32)) {
        do {
            if (_wcsicmp(pe32.szExeFile, GAME_PROCESS_NAME) == 0) {
                pid = pe32.th32ProcessID;
                break;
            }
        } while (Process32NextW(hSnapshot, &pe32));
    }

    CloseHandle(hSnapshot);
    return pid;
}

// 查找游戏窗口的回调数据
struct FindWindowData {
    DWORD pid;
    HWND hwnd;
};

// 枚举窗口回调
static BOOL CALLBACK EnumWindowsProc(HWND hwnd, LPARAM lParam) {
    FindWindowData* data = (FindWindowData*)lParam;

    DWORD windowPid;
    GetWindowThreadProcessId(hwnd, &windowPid);

    if (windowPid == data->pid) {
        wchar_t className[256];
        if (GetClassNameW(hwnd, className, 256)) {
            if (wcscmp(className, GAME_WINDOW_CLASS) == 0) {
                data->hwnd = hwnd;
                return FALSE;  // 停止枚举
            }
        }
    }

    return TRUE;  // 继续枚举
}

// 查找游戏窗口
static HWND FindGameWindow(DWORD pid) {
    FindWindowData data = { pid, NULL };
    EnumWindows(EnumWindowsProc, (LPARAM)&data);
    return data.hwnd;
}

// 设置 DPI 感知
static void SetDpiAwareness() {
    // 设置线程 DPI 感知为 Per-Monitor V2
    // 这确保 API 返回物理像素坐标
    SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
}

// 前向声明
static bool ReconnectToGame(MsaControllerContext* ctx);

// 确保控制器连接有效（包括游戏重启后的重连）
static bool EnsureConnection(MsaControllerContext* ctx) {
    if (!ctx || !ctx->connected) {
        return false;
    }

    // 检查注入器是否有效
    if (ctx->injectorCtx && Injector_IsProcessAlive(ctx->injectorCtx)) {
        // 进程存活，确保注入状态
        return Injector_EnsureInjection(ctx->injectorCtx);
    }

    // 进程已退出，尝试重新连接
    LOG("检测到游戏进程已退出，尝试重新连接...");
    return ReconnectToGame(ctx);
}

// 重新连接到游戏（游戏重启后调用）
static bool ReconnectToGame(MsaControllerContext* ctx) {
    if (!ctx) {
        return false;
    }

    // 查找新的游戏进程
    DWORD newPid = FindGameProcess();
    if (newPid == 0) {
        LOG_ERROR("未找到游戏进程，请确保游戏已启动");
        return false;
    }
    LOG("找到新的游戏进程，PID: %lu", newPid);

    // 查找新的游戏窗口
    HWND newHwnd = FindGameWindow(newPid);
    if (newHwnd == NULL) {
        LOG_ERROR("未找到游戏窗口");
        return false;
    }
    LOG("找到新的游戏窗口，句柄: 0x%p", newHwnd);

    // 更新上下文
    ctx->pid = newPid;
    ctx->hwnd = newHwnd;

    // 更新共享内存
    ControllerSharedMemory_SetGameHwnd(newHwnd);
    ControllerSharedMemory_SetInjectedPid(newPid);

    // 更新注入器并重新注入
    if (ctx->injectorCtx) {
        Injector_SetPid(ctx->injectorCtx, newPid);
        if (!Injector_Inject(ctx->injectorCtx)) {
            LOG_ERROR("重新注入 Hook DLL 失败");
            return false;
        }
        LOG("Hook DLL 重新注入成功");
    }

    // 等待 DLL 初始化
    Sleep(100);

    // 重新创建截图器
    if (ctx->screencapCtx) {
        Screencap_Destroy(ctx->screencapCtx);
        ctx->screencapCtx = NULL;
    }

    ctx->screencapCtx = Screencap_Create(newHwnd);
    if (ctx->screencapCtx == NULL) {
        LOG_ERROR("重新创建截图器失败");
        return false;
    }
    LOG("截图器重新创建成功");

    // 更新 UUID
    snprintf(ctx->uuid, sizeof(ctx->uuid), "MSA_Controller_%lu_%p", ctx->pid, ctx->hwnd);

    LOG("重新连接成功！");
    return true;
}

// ==================== 回调实现 ====================

// connect 回调
static MaaBool callback_connect(void* trans_arg) {
    MsaControllerContext* ctx = (MsaControllerContext*)trans_arg;
    if (!ctx) {
        return false;
    }

    LOG("正在连接...");

    // 设置 DPI 感知
    SetDpiAwareness();
    LOG("已设置 DPI 感知: Per-Monitor V2");

    // 如果没有指定窗口句柄，自动查找
    if (ctx->hwnd == NULL) {
        // 查找游戏进程
        ctx->pid = FindGameProcess();
        if (ctx->pid == 0) {
            LOG_ERROR("未找到游戏进程");
            return false;
        }
        LOG("找到游戏进程，PID: %lu", ctx->pid);

        // 查找游戏窗口
        ctx->hwnd = FindGameWindow(ctx->pid);
        if (ctx->hwnd == NULL) {
            LOG_ERROR("未找到游戏窗口");
            return false;
        }
        LOG("找到游戏窗口，句柄: 0x%p", ctx->hwnd);
    } else {
        // 从窗口句柄获取 PID
        GetWindowThreadProcessId(ctx->hwnd, &ctx->pid);
        LOG("使用指定窗口，句柄: 0x%p, PID: %lu", ctx->hwnd, ctx->pid);
    }

    // 初始化共享内存
    if (!ControllerSharedMemory_Init()) {
        LOG_ERROR("初始化共享内存失败");
        return false;
    }
    LOG("共享内存初始化成功");

    // 设置共享内存数据
    ControllerSharedMemory_SetGameHwnd(ctx->hwnd);
    ControllerSharedMemory_SetInjectedPid(ctx->pid);

    // 创建注入器并执行首次注入
    wchar_t dllPath[MAX_PATH];
    if (!Injector_GetDefaultDllPath(dllPath, MAX_PATH)) {
        LOG_ERROR("获取 Hook DLL 路径失败");
        ControllerSharedMemory_Cleanup();
        return false;
    }
    LOG("Hook DLL 路径: %ls", dllPath);

    ctx->injectorCtx = Injector_Create(ctx->pid, dllPath);
    if (!ctx->injectorCtx) {
        LOG_ERROR("创建注入器失败");
        ControllerSharedMemory_Cleanup();
        return false;
    }

    if (!Injector_Inject(ctx->injectorCtx)) {
        LOG_ERROR("注入 Hook DLL 失败");
        Injector_Destroy(ctx->injectorCtx);
        ctx->injectorCtx = NULL;
        ControllerSharedMemory_Cleanup();
        return false;
    }
    LOG("Hook DLL 注入成功");

    // 等待 DLL 初始化
    Sleep(100);

    // 创建截图器
    ctx->screencapCtx = Screencap_Create(ctx->hwnd);
    if (ctx->screencapCtx == NULL) {
        LOG_ERROR("创建截图器失败");
        Injector_Destroy(ctx->injectorCtx);
        ctx->injectorCtx = NULL;
        ControllerSharedMemory_Cleanup();
        return false;
    }
    LOG("截图器创建成功");

    // 生成 UUID
    snprintf(ctx->uuid, sizeof(ctx->uuid), "MSA_Controller_%lu_%p", ctx->pid, ctx->hwnd);

    ctx->connected = true;
    LOG("连接成功");
    return true;
}

// request_uuid 回调
static MaaBool callback_request_uuid(void* trans_arg, MaaStringBuffer* buffer) {
    MsaControllerContext* ctx = (MsaControllerContext*)trans_arg;
    if (!ctx || !buffer) {
        return false;
    }

    MaaStringBufferSet(buffer, ctx->uuid);
    return true;
}

// get_features 回调
static MaaControllerFeature callback_get_features(void* trans_arg) {
    (void)trans_arg;
    // 返回 0 表示使用默认行为
    return MaaControllerFeature_None;
}

// screencap 回调
static MaaBool callback_screencap(void* trans_arg, MaaImageBuffer* buffer) {
    MsaControllerContext* ctx = (MsaControllerContext*)trans_arg;
    if (!ctx || !buffer) {
        return false;
    }

    // 确保连接有效（包括游戏重启后的重连）
    if (!EnsureConnection(ctx)) {
        LOG_ERROR("连接无效，无法执行截图");
        return false;
    }

    if (!ctx->screencapCtx) {
        LOG_ERROR("截图器未初始化");
        return false;
    }

    uint8_t* data = NULL;
    int width = 0, height = 0;

    if (!Screencap_Capture(ctx->screencapCtx, &data, &width, &height)) {
        LOG_ERROR("截图失败");
        return false;
    }

    // 将 BGRA 数据设置到 MaaImageBuffer
    // MaaImageBuffer 使用 OpenCV 的 cv::Mat 格式
    // type = CV_8UC4 = 24 (8位无符号，4通道)
    const int CV_8UC4 = 24;
    MaaBool result = MaaImageBufferSetRawData(buffer, data, width, height, CV_8UC4);

    Screencap_FreeData(data);
    return result;
}

// click 回调
static MaaBool callback_click(int32_t x, int32_t y, void* trans_arg) {
    MsaControllerContext* ctx = (MsaControllerContext*)trans_arg;
    if (!ctx || !ctx->connected) {
        LOG_ERROR("控制器未连接");
        return false;
    }

    // 确保连接有效（包括游戏重启后的重连）
    if (!EnsureConnection(ctx)) {
        LOG_ERROR("连接无效，无法执行点击");
        return false;
    }

    LOG("执行点击: (%d, %d)", x, y);

    // 1. 写入坐标到共享内存
    ControllerSharedMemory_SetTargetPos(x, y);

    // 2. 启用 Hook
    ControllerSharedMemory_SetEnabled(true);

    // 3. 发送 WM_ACTIVATE 伪造激活状态
    SendMessageW(ctx->hwnd, WM_ACTIVATE, WA_ACTIVE, 0);

    // 4. 计算 lParam（坐标打包）
    LPARAM lParam = MAKELPARAM(x, y);

    // 5. 发送鼠标按下消息
    SendMessageW(ctx->hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lParam);

    // 6. 短暂延迟
    Sleep(50);

    // 7. 发送鼠标抬起消息
    SendMessageW(ctx->hwnd, WM_LBUTTONUP, 0, lParam);

    // 8. 禁用 Hook
    ControllerSharedMemory_SetEnabled(false);

    LOG("点击完成");
    return true;
}

// swipe 回调
static MaaBool callback_swipe(int32_t x1, int32_t y1, int32_t x2, int32_t y2, int32_t duration, void* trans_arg) {
    MsaControllerContext* ctx = (MsaControllerContext*)trans_arg;
    if (!ctx || !ctx->connected) {
        LOG_ERROR("控制器未连接");
        return false;
    }

    // 确保连接有效（包括游戏重启后的重连）
    if (!EnsureConnection(ctx)) {
        LOG_ERROR("连接无效，无法执行滑动");
        return false;
    }

    LOG("执行滑动: (%d, %d) -> (%d, %d), 时长: %d ms", x1, y1, x2, y2, duration);

    // 计算步数和每步延迟
    const int steps = 20;  // 分成 20 步
    int stepDelay = duration / steps;
    if (stepDelay < 5) stepDelay = 5;  // 最小延迟 5ms

    float dx = (float)(x2 - x1) / steps;
    float dy = (float)(y2 - y1) / steps;

    // 启用 Hook
    ControllerSharedMemory_SetEnabled(true);

    // 发送 WM_ACTIVATE 伪造激活状态
    SendMessageW(ctx->hwnd, WM_ACTIVATE, WA_ACTIVE, 0);

    // 起始位置按下
    ControllerSharedMemory_SetTargetPos(x1, y1);
    LPARAM lParam = MAKELPARAM(x1, y1);
    SendMessageW(ctx->hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lParam);

    // 逐步移动
    for (int i = 1; i <= steps; ++i) {
        int currentX = x1 + (int)(dx * i);
        int currentY = y1 + (int)(dy * i);

        ControllerSharedMemory_SetTargetPos(currentX, currentY);
        lParam = MAKELPARAM(currentX, currentY);
        SendMessageW(ctx->hwnd, WM_MOUSEMOVE, MK_LBUTTON, lParam);

        Sleep(stepDelay);
    }

    // 终点位置抬起
    ControllerSharedMemory_SetTargetPos(x2, y2);
    lParam = MAKELPARAM(x2, y2);
    SendMessageW(ctx->hwnd, WM_LBUTTONUP, 0, lParam);

    // 禁用 Hook
    ControllerSharedMemory_SetEnabled(false);

    LOG("滑动完成");
    return true;
}

// touch_down 回调
static MaaBool callback_touch_down(int32_t contact, int32_t x, int32_t y, int32_t pressure, void* trans_arg) {
    (void)contact;
    (void)pressure;

    MsaControllerContext* ctx = (MsaControllerContext*)trans_arg;
    if (!ctx || !ctx->connected) {
        return false;
    }

    // 确保连接有效（包括游戏重启后的重连）
    if (!EnsureConnection(ctx)) {
        return false;
    }

    // 写入坐标并启用 Hook
    ControllerSharedMemory_SetTargetPos(x, y);
    ControllerSharedMemory_SetEnabled(true);

    // 发送激活和按下消息
    SendMessageW(ctx->hwnd, WM_ACTIVATE, WA_ACTIVE, 0);
    LPARAM lParam = MAKELPARAM(x, y);
    SendMessageW(ctx->hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lParam);

    return true;
}

// touch_move 回调
static MaaBool callback_touch_move(int32_t contact, int32_t x, int32_t y, int32_t pressure, void* trans_arg) {
    (void)contact;
    (void)pressure;

    MsaControllerContext* ctx = (MsaControllerContext*)trans_arg;
    if (!ctx || !ctx->connected) {
        return false;
    }

    // 更新坐标
    ControllerSharedMemory_SetTargetPos(x, y);

    // 发送移动消息
    LPARAM lParam = MAKELPARAM(x, y);
    SendMessageW(ctx->hwnd, WM_MOUSEMOVE, MK_LBUTTON, lParam);

    return true;
}

// touch_up 回调
static MaaBool callback_touch_up(int32_t contact, void* trans_arg) {
    (void)contact;

    MsaControllerContext* ctx = (MsaControllerContext*)trans_arg;
    if (!ctx || !ctx->connected) {
        return false;
    }

    // 获取当前坐标
    PMSA_SHARED_DATA data = ControllerSharedMemory_GetData();
    int x = data ? data->target_x : 0;
    int y = data ? data->target_y : 0;

    // 发送抬起消息
    LPARAM lParam = MAKELPARAM(x, y);
    SendMessageW(ctx->hwnd, WM_LBUTTONUP, 0, lParam);

    // 禁用 Hook
    ControllerSharedMemory_SetEnabled(false);

    return true;
}

// 其他回调（暂不实现）
static MaaBool callback_start_app(const char* intent, void* trans_arg) {
    (void)intent;
    (void)trans_arg;
    return false;
}

static MaaBool callback_stop_app(const char* intent, void* trans_arg) {
    (void)intent;
    (void)trans_arg;
    return false;
}

static MaaBool callback_click_key(int32_t keycode, void* trans_arg) {
    (void)keycode;
    (void)trans_arg;
    return false;
}

static MaaBool callback_input_text(const char* text, void* trans_arg) {
    (void)text;
    (void)trans_arg;
    return false;
}

static MaaBool callback_key_down(int32_t keycode, void* trans_arg) {
    (void)keycode;
    (void)trans_arg;
    return false;
}

static MaaBool callback_key_up(int32_t keycode, void* trans_arg) {
    (void)keycode;
    (void)trans_arg;
    return false;
}

static MaaBool callback_scroll(int32_t dx, int32_t dy, void* trans_arg) {
    (void)dx;
    (void)dy;
    (void)trans_arg;
    return false;
}

// ==================== 公共 API ====================

MsaControllerContext* MsaController_Create(HWND hwnd) {
    MsaControllerContext* ctx = (MsaControllerContext*)calloc(1, sizeof(MsaControllerContext));
    if (!ctx) {
        return NULL;
    }

    ctx->hwnd = hwnd;
    ctx->connected = false;

    // 初始化回调结构
    ctx->callbacks.connect = callback_connect;
    ctx->callbacks.request_uuid = callback_request_uuid;
    ctx->callbacks.get_features = callback_get_features;
    ctx->callbacks.start_app = callback_start_app;
    ctx->callbacks.stop_app = callback_stop_app;
    ctx->callbacks.screencap = callback_screencap;
    ctx->callbacks.click = callback_click;
    ctx->callbacks.swipe = callback_swipe;
    ctx->callbacks.touch_down = callback_touch_down;
    ctx->callbacks.touch_move = callback_touch_move;
    ctx->callbacks.touch_up = callback_touch_up;
    ctx->callbacks.click_key = callback_click_key;
    ctx->callbacks.input_text = callback_input_text;
    ctx->callbacks.key_down = callback_key_down;
    ctx->callbacks.key_up = callback_key_up;
    ctx->callbacks.scroll = callback_scroll;

    return ctx;
}

void MsaController_Destroy(MsaControllerContext* ctx) {
    if (!ctx) {
        return;
    }

    // 销毁截图器
    if (ctx->screencapCtx) {
        Screencap_Destroy(ctx->screencapCtx);
        ctx->screencapCtx = NULL;
    }

    // 销毁注入器
    if (ctx->injectorCtx) {
        Injector_Destroy(ctx->injectorCtx);
        ctx->injectorCtx = NULL;
    }

    // 清理共享内存
    ControllerSharedMemory_Cleanup();

    free(ctx);
}

MaaCustomControllerCallbacks* MsaController_GetCallbacks(MsaControllerContext* ctx) {
    if (!ctx) {
        return NULL;
    }
    return &ctx->callbacks;
}

void* MsaController_GetTransArg(MsaControllerContext* ctx) {
    return ctx;
}

MaaController* MsaController_CreateMaaController(HWND hwnd) {
    MsaControllerContext* ctx = MsaController_Create(hwnd);
    if (!ctx) {
        return NULL;
    }

    MaaController* controller = MaaCustomControllerCreate(
        MsaController_GetCallbacks(ctx),
        MsaController_GetTransArg(ctx)
    );

    if (!controller) {
        MsaController_Destroy(ctx);
        return NULL;
    }

    // 注意：这里有一个问题 - ctx 的生命周期需要与 controller 一致
    // 在实际使用中，需要在 controller 销毁时也销毁 ctx
    // 这里暂时不处理，后续可以通过其他方式管理

    return controller;
}
