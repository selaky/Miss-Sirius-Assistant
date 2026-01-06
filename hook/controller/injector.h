/**
 * MSA 自定义控制器 - DLL 注入器
 *
 * 负责将 Hook DLL 注入到游戏进程
 * 使用 CreateRemoteThread + LoadLibraryW 方式注入
 */

#pragma once

#include <windows.h>

// 注入器上下文
typedef struct InjectorContext InjectorContext;

// 创建注入器上下文
// pid: 目标进程 PID
// dllPath: Hook DLL 的完整路径
InjectorContext* Injector_Create(DWORD pid, const wchar_t* dllPath);

// 销毁注入器上下文
void Injector_Destroy(InjectorContext* ctx);

// 执行注入
// 返回: 成功返回 true，失败返回 false
bool Injector_Inject(InjectorContext* ctx);

// 检查 DLL 是否已注入
bool Injector_IsInjected(InjectorContext* ctx);

// 确保注入状态有效
// 如果进程已退出或 DLL 未注入，则重新注入
// 返回: 注入状态有效返回 true，失败返回 false
bool Injector_EnsureInjection(InjectorContext* ctx);

// 检查目标进程是否存活
bool Injector_IsProcessAlive(InjectorContext* ctx);

// 获取目标进程 PID
DWORD Injector_GetPid(InjectorContext* ctx);

// 更新目标进程 PID（用于游戏重启后重新注入）
void Injector_SetPid(InjectorContext* ctx, DWORD pid);

// 获取 Hook DLL 路径
// 根据当前模块路径自动计算 msa_hook.dll 的位置
// buffer: 输出缓冲区
// bufferSize: 缓冲区大小（字符数）
// 返回: 成功返回 true
bool Injector_GetDefaultDllPath(wchar_t* buffer, size_t bufferSize);
