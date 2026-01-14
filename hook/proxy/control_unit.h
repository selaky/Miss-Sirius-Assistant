/**
 * MSA Proxy DLL - 自定义控制单元
 *
 * 继承 Win32ControlUnitAPI，截图委托原版，输入使用自定义实现
 */

#pragma once

#include <string>
#include <memory>
#include <windows.h>

// MAA Framework 类型定义
#include "MaaFramework/MaaDef.h"

// 前向声明
class SharedMemoryManager;
class Injector;

// OpenCV Mat 前向声明
namespace cv {
class Mat;
}

// MAA 命名空间定义
#define MAA_NS maa
#define MAA_CTRL_UNIT_NS MAA_NS::CtrlUnitNs

namespace MAA_CTRL_UNIT_NS {

/**
 * 控制单元基类接口
 * 与 MAA Framework 的 ControlUnitAPI 保持 ABI 兼容
 */
class ControlUnitAPI
{
public:
    virtual ~ControlUnitAPI() = default;

    virtual bool connect() = 0;
    virtual bool connected() const = 0;  // v5.4.0 新增
    virtual bool request_uuid(std::string& uuid) = 0;
    virtual MaaControllerFeature get_features() const = 0;
    virtual bool start_app(const std::string& intent) = 0;
    virtual bool stop_app(const std::string& intent) = 0;
    virtual bool screencap(cv::Mat& image) = 0;
    virtual bool click(int x, int y) = 0;
    virtual bool swipe(int x1, int y1, int x2, int y2, int duration) = 0;
    virtual bool touch_down(int contact, int x, int y, int pressure) = 0;
    virtual bool touch_move(int contact, int x, int y, int pressure) = 0;
    virtual bool touch_up(int contact) = 0;
    virtual bool click_key(int key) = 0;
    virtual bool input_text(const std::string& text) = 0;
    virtual bool key_down(int key) = 0;
    virtual bool key_up(int key) = 0;
    virtual bool scroll(int dx, int dy) = 0;
};

/**
 * Win32 控制单元接口
 * 空派生，仅用于类型区分
 */
class Win32ControlUnitAPI : public ControlUnitAPI
{
public:
    virtual ~Win32ControlUnitAPI() = default;
};

} // namespace MAA_CTRL_UNIT_NS

// Handle 类型定义
using MaaWin32ControlUnitHandle = MAA_CTRL_UNIT_NS::Win32ControlUnitAPI*;

/**
 * MSA 自定义控制单元
 *
 * 包装原版控制单元，截图委托原版，输入使用自定义实现（后台点击）
 */
class MsaControlUnit : public MAA_CTRL_UNIT_NS::Win32ControlUnitAPI
{
public:
    /**
     * 构造函数
     * @param original 原版控制单元指针
     * @param hwnd 游戏窗口句柄
     */
    MsaControlUnit(MAA_CTRL_UNIT_NS::Win32ControlUnitAPI* original, HWND hwnd);

    ~MsaControlUnit() override;

    // ========== 委托给原版的方法 ==========

    bool connect() override;
    bool connected() const override;  // v5.4.0 新增
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

    // ========== 自定义实现的方法（阶段四实现） ==========

    bool click(int x, int y) override;
    bool swipe(int x1, int y1, int x2, int y2, int duration) override;
    bool touch_down(int contact, int x, int y, int pressure) override;
    bool touch_move(int contact, int x, int y, int pressure) override;
    bool touch_up(int contact) override;

    /**
     * 获取原版控制单元指针
     * 用于销毁时调用原版 Destroy
     */
    MAA_CTRL_UNIT_NS::Win32ControlUnitAPI* get_original() const { return original_; }

private:
    /**
     * 确保注入已完成
     * @return 是否成功
     */
    bool ensure_injected();

    /**
     * 执行后台点击
     * @param x X 坐标（客户区）
     * @param y Y 坐标（客户区）
     * @return 是否成功
     */
    bool do_background_click(int x, int y);

    /**
     * 获取 Hook DLL 的完整路径
     * @return DLL 路径
     */
    std::wstring get_hook_dll_path();

    // 原版控制单元
    MAA_CTRL_UNIT_NS::Win32ControlUnitAPI* original_;

    // 游戏窗口句柄
    HWND hwnd_;

    // 共享内存管理器
    std::unique_ptr<SharedMemoryManager> shared_memory_;

    // DLL 注入器
    std::unique_ptr<Injector> injector_;

    // 注入状态
    bool injected_;
};
