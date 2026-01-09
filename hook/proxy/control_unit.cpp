/**
 * MSA Proxy DLL - 自定义控制单元实现
 *
 * 截图委托原版，输入使用自定义实现（后台点击）
 */

#include "control_unit.h"
#include "shared_memory.h"
#include "injector.h"

#include <cmath>

// OpenCV Mat 头文件
#ifdef _MSC_VER
#pragma warning(push)
#pragma warning(disable : 4819) // 忽略代码页警告
#endif

#include <opencv2/core/mat.hpp>

#ifdef _MSC_VER
#pragma warning(pop)
#endif

// ========== 构造与析构 ==========

MsaControlUnit::MsaControlUnit(MAA_CTRL_UNIT_NS::Win32ControlUnitAPI* original, HWND hwnd)
    : original_(original)
    , hwnd_(hwnd)
    , shared_memory_(std::make_unique<SharedMemoryManager>())
    , injector_(std::make_unique<Injector>())
    , injected_(false)
{
}

MsaControlUnit::~MsaControlUnit()
{
    // 禁用 Hook
    if (shared_memory_ && shared_memory_->is_valid()) {
        shared_memory_->disable();
    }
    // 注意：不要在这里删除 original_，由 Destroy 函数负责
}

// ========== 委托给原版的方法 ==========

bool MsaControlUnit::connect()
{
    // 委托原版
    bool result = original_->connect();

    if (result) {
        // 初始化共享内存
        if (!shared_memory_->init(hwnd_)) {
            // 共享内存初始化失败，但不影响连接结果
            // 后续点击时会再次尝试
        }
    }

    return result;
}

bool MsaControlUnit::request_uuid(std::string& uuid)
{
    return original_->request_uuid(uuid);
}

MaaControllerFeature MsaControlUnit::get_features() const
{
    return original_->get_features();
}

bool MsaControlUnit::start_app(const std::string& intent)
{
    return original_->start_app(intent);
}

bool MsaControlUnit::stop_app(const std::string& intent)
{
    return original_->stop_app(intent);
}

bool MsaControlUnit::screencap(cv::Mat& image)
{
    return original_->screencap(image);
}

bool MsaControlUnit::click_key(int key)
{
    return original_->click_key(key);
}

bool MsaControlUnit::input_text(const std::string& text)
{
    return original_->input_text(text);
}

bool MsaControlUnit::key_down(int key)
{
    return original_->key_down(key);
}

bool MsaControlUnit::key_up(int key)
{
    return original_->key_up(key);
}

bool MsaControlUnit::scroll(int dx, int dy)
{
    return original_->scroll(dx, dy);
}

// ========== 自定义实现的方法 ==========

bool MsaControlUnit::click(int x, int y)
{
    // 使用自定义后台点击
    return do_background_click(x, y);
}

bool MsaControlUnit::swipe(int x1, int y1, int x2, int y2, int duration)
{
    // 滑动实现：分解为多个点击移动
    // 简化实现：起点按下 -> 移动 -> 终点抬起
    if (!ensure_injected()) {
        return original_->swipe(x1, y1, x2, y2, duration);
    }

    // 计算步数（根据距离和时长）
    int dx = x2 - x1;
    int dy = y2 - y1;
    int distance = (int)sqrt((double)(dx * dx + dy * dy));
    int steps = (distance > 0) ? (duration / 10) : 1;  // 每 10ms 一步
    if (steps < 2) steps = 2;
    if (steps > 100) steps = 100;

    // 按下
    if (!touch_down(0, x1, y1, 0)) {
        return false;
    }

    // 移动
    for (int i = 1; i < steps; i++) {
        int x = x1 + dx * i / steps;
        int y = y1 + dy * i / steps;
        if (!touch_move(0, x, y, 0)) {
            touch_up(0);
            return false;
        }
        Sleep(duration / steps);
    }

    // 抬起
    return touch_up(0);
}

bool MsaControlUnit::touch_down(int contact, int x, int y, int pressure)
{
    (void)contact;
    (void)pressure;

    if (!ensure_injected()) {
        OutputDebugStringW(L"[MSA] touch_down: 注入失败，回退到原版实现\n");
        return original_->touch_down(contact, x, y, pressure);
    }

    // 设置目标坐标
    shared_memory_->set_target(x, y);
    shared_memory_->enable();

    // 诊断日志
    wchar_t log_buffer[256];
    swprintf_s(log_buffer, L"[MSA] touch_down: (%d, %d), contact=%d\n", x, y, contact);
    OutputDebugStringW(log_buffer);

    // 发送 WM_ACTIVATE 伪造激活
    SendMessageW(hwnd_, WM_ACTIVATE, WA_ACTIVE, 0);

    // 发送鼠标按下消息
    LPARAM lParam = MAKELPARAM(x, y);
    SendMessageW(hwnd_, WM_LBUTTONDOWN, MK_LBUTTON, lParam);

    return true;
}

bool MsaControlUnit::touch_move(int contact, int x, int y, int pressure)
{
    (void)contact;
    (void)pressure;

    if (!shared_memory_->is_valid()) {
        return original_->touch_move(contact, x, y, pressure);
    }

    // 更新目标坐标
    shared_memory_->set_target(x, y);

    // 诊断日志
    wchar_t log_buffer[256];
    swprintf_s(log_buffer, L"[MSA] touch_move: (%d, %d), contact=%d\n", x, y, contact);
    OutputDebugStringW(log_buffer);

    // 发送鼠标移动消息
    LPARAM lParam = MAKELPARAM(x, y);
    SendMessageW(hwnd_, WM_MOUSEMOVE, MK_LBUTTON, lParam);

    return true;
}

bool MsaControlUnit::touch_up(int contact)
{
    (void)contact;

    if (!shared_memory_->is_valid()) {
        return original_->touch_up(contact);
    }

    // 诊断日志
    wchar_t log_buffer[256];
    swprintf_s(log_buffer, L"[MSA] touch_up: contact=%d\n", contact);
    OutputDebugStringW(log_buffer);

    // 发送鼠标抬起消息（使用当前坐标）
    LPARAM lParam = MAKELPARAM(0, 0);  // 坐标在 touch_down/move 中已设置
    DWORD tick_up = GetTickCount();
    SendMessageW(hwnd_, WM_LBUTTONUP, 0, lParam);
    swprintf_s(log_buffer, L"[MSA] WM_LBUTTONUP 发送完成, tick=%u\n", tick_up);
    OutputDebugStringW(log_buffer);

    // 延迟禁用 Hook：等待游戏采样鼠标位置
    Sleep(50);

    // 禁用 Hook
    shared_memory_->disable();
    OutputDebugStringW(L"[MSA] touch_up: Hook 已禁用\n");

    return true;
}

// ========== 私有方法 ==========

bool MsaControlUnit::ensure_injected()
{
    // 检查共享内存是否有效
    if (!shared_memory_->is_valid()) {
        if (!shared_memory_->init(hwnd_)) {
            return false;
        }
    }

    // 检查注入是否仍然有效
    if (injected_ && injector_->is_valid()) {
        return true;
    }

    // 需要重新注入
    std::wstring dll_path = get_hook_dll_path();
    if (dll_path.empty()) {
        return false;
    }

    if (!injector_->inject(hwnd_, dll_path)) {
        return false;
    }

    // 更新共享内存中的 PID
    shared_memory_->set_injected_pid(injector_->get_injected_pid());
    injected_ = true;

    // 等待 Hook DLL 初始化
    Sleep(100);

    return true;
}

bool MsaControlUnit::do_background_click(int x, int y)
{
    // 确保注入已完成
    if (!ensure_injected()) {
        // 注入失败，回退到原版实现
        OutputDebugStringW(L"[MSA] 后台点击: 注入失败，回退到原版实现\n");
        return original_->click(x, y);
    }

    // 设置目标坐标
    shared_memory_->set_target(x, y);

    // 启用 Hook
    shared_memory_->enable();

    // 诊断日志：点击开始
    wchar_t log_buffer[256];
    swprintf_s(log_buffer, L"[MSA] 后台点击开始: (%d, %d)\n", x, y);
    OutputDebugStringW(log_buffer);

    // 发送 WM_ACTIVATE 伪造激活
    SendMessageW(hwnd_, WM_ACTIVATE, WA_ACTIVE, 0);

    // 发送鼠标按下消息
    LPARAM lParam = MAKELPARAM(x, y);
    DWORD tick_down = GetTickCount();
    SendMessageW(hwnd_, WM_LBUTTONDOWN, MK_LBUTTON, lParam);
    swprintf_s(log_buffer, L"[MSA] WM_LBUTTONDOWN 发送完成, tick=%u\n", tick_down);
    OutputDebugStringW(log_buffer);

    // 按下/抬起延迟：50ms
    Sleep(50);

    // 发送鼠标抬起消息
    DWORD tick_up = GetTickCount();
    SendMessageW(hwnd_, WM_LBUTTONUP, 0, lParam);
    swprintf_s(log_buffer, L"[MSA] WM_LBUTTONUP 发送完成, tick=%u, 间隔=%ums\n",
               tick_up, tick_up - tick_down);
    OutputDebugStringW(log_buffer);

    // 延迟禁用 Hook：等待游戏采样鼠标位置
    Sleep(50);

    // 禁用 Hook
    shared_memory_->disable();
    OutputDebugStringW(L"[MSA] Hook 已禁用，点击流程结束\n");

    return true;
}

std::wstring MsaControlUnit::get_hook_dll_path()
{
    // 获取当前 DLL 所在目录
    wchar_t module_path[MAX_PATH] = { 0 };
    HMODULE hModule = NULL;

    // 获取当前 DLL 的模块句柄
    // 使用一个静态变量的地址来定位当前模块
    static int dummy = 0;
    if (!GetModuleHandleExW(
            GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            (LPCWSTR)&dummy,
            &hModule)) {
        return L"";
    }

    // 获取 DLL 完整路径
    if (GetModuleFileNameW(hModule, module_path, MAX_PATH) == 0) {
        return L"";
    }

    // 提取目录部分
    std::wstring path(module_path);
    size_t pos = path.find_last_of(L"\\/");
    if (pos == std::wstring::npos) {
        return L"";
    }

    // 构造 Hook DLL 路径
    return path.substr(0, pos + 1) + L"msa_hook.dll";
}
