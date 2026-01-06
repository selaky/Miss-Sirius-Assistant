/**
 * MSA 自定义控制器 - DLL 注入器实现
 */

#include "injector.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <tlhelp32.h>

// 日志宏
#define LOG(fmt, ...) printf("[MSA Injector] " fmt "\n", ##__VA_ARGS__)
#define LOG_ERROR(fmt, ...) printf("[MSA Injector Error] " fmt " (错误码: %lu)\n", ##__VA_ARGS__, GetLastError())

// 注入器上下文
struct InjectorContext {
    DWORD pid;                      // 目标进程 PID
    wchar_t dllPath[MAX_PATH];      // Hook DLL 路径
    bool injected;                  // 是否已注入
};

// 检查 DLL 是否已加载到目标进程
static bool IsDllLoaded(DWORD pid, const wchar_t* dllName) {
    HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid);
    if (hSnapshot == INVALID_HANDLE_VALUE) {
        return false;
    }

    MODULEENTRY32W me32;
    me32.dwSize = sizeof(me32);

    bool found = false;
    if (Module32FirstW(hSnapshot, &me32)) {
        do {
            if (_wcsicmp(me32.szModule, dllName) == 0) {
                found = true;
                break;
            }
        } while (Module32NextW(hSnapshot, &me32));
    }

    CloseHandle(hSnapshot);
    return found;
}

// 从完整路径提取文件名
static const wchar_t* GetFileName(const wchar_t* path) {
    const wchar_t* lastSlash = wcsrchr(path, L'\\');
    if (lastSlash != NULL) {
        return lastSlash + 1;
    }
    return path;
}

InjectorContext* Injector_Create(DWORD pid, const wchar_t* dllPath) {
    if (pid == 0 || dllPath == NULL) {
        return NULL;
    }

    InjectorContext* ctx = (InjectorContext*)calloc(1, sizeof(InjectorContext));
    if (!ctx) {
        return NULL;
    }

    ctx->pid = pid;
    wcscpy_s(ctx->dllPath, MAX_PATH, dllPath);
    ctx->injected = false;

    return ctx;
}

void Injector_Destroy(InjectorContext* ctx) {
    if (ctx) {
        free(ctx);
    }
}

bool Injector_Inject(InjectorContext* ctx) {
    if (!ctx) {
        return false;
    }

    const wchar_t* dllName = GetFileName(ctx->dllPath);

    // 检查是否已经注入
    if (IsDllLoaded(ctx->pid, dllName)) {
        LOG("DLL 已经注入，跳过注入步骤");
        ctx->injected = true;
        return true;
    }

    // 检查 DLL 文件是否存在
    if (GetFileAttributesW(ctx->dllPath) == INVALID_FILE_ATTRIBUTES) {
        LOG_ERROR("DLL 文件不存在: %ls", ctx->dllPath);
        return false;
    }

    // 打开目标进程
    HANDLE hProcess = OpenProcess(
        PROCESS_CREATE_THREAD | PROCESS_QUERY_INFORMATION |
        PROCESS_VM_OPERATION | PROCESS_VM_WRITE | PROCESS_VM_READ,
        FALSE,
        ctx->pid
    );

    if (hProcess == NULL) {
        LOG_ERROR("打开游戏进程失败，请以管理员身份运行");
        return false;
    }

    // 在目标进程中分配内存
    size_t pathSize = (wcslen(ctx->dllPath) + 1) * sizeof(wchar_t);
    LPVOID pRemotePath = VirtualAllocEx(
        hProcess,
        NULL,
        pathSize,
        MEM_COMMIT | MEM_RESERVE,
        PAGE_READWRITE
    );

    if (pRemotePath == NULL) {
        LOG_ERROR("在目标进程中分配内存失败");
        CloseHandle(hProcess);
        return false;
    }

    // 写入 DLL 路径
    if (!WriteProcessMemory(hProcess, pRemotePath, ctx->dllPath, pathSize, NULL)) {
        LOG_ERROR("写入 DLL 路径失败");
        VirtualFreeEx(hProcess, pRemotePath, 0, MEM_RELEASE);
        CloseHandle(hProcess);
        return false;
    }

    // 获取 LoadLibraryW 地址
    HMODULE hKernel32 = GetModuleHandleW(L"kernel32.dll");
    LPTHREAD_START_ROUTINE pLoadLibraryW = (LPTHREAD_START_ROUTINE)GetProcAddress(hKernel32, "LoadLibraryW");

    if (pLoadLibraryW == NULL) {
        LOG_ERROR("获取 LoadLibraryW 地址失败");
        VirtualFreeEx(hProcess, pRemotePath, 0, MEM_RELEASE);
        CloseHandle(hProcess);
        return false;
    }

    // 创建远程线程执行 LoadLibraryW
    HANDLE hThread = CreateRemoteThread(
        hProcess,
        NULL,
        0,
        pLoadLibraryW,
        pRemotePath,
        0,
        NULL
    );

    if (hThread == NULL) {
        LOG_ERROR("创建远程线程失败");
        VirtualFreeEx(hProcess, pRemotePath, 0, MEM_RELEASE);
        CloseHandle(hProcess);
        return false;
    }

    // 等待线程完成
    DWORD waitResult = WaitForSingleObject(hThread, 5000);
    if (waitResult == WAIT_TIMEOUT) {
        LOG_ERROR("等待注入线程超时");
        CloseHandle(hThread);
        VirtualFreeEx(hProcess, pRemotePath, 0, MEM_RELEASE);
        CloseHandle(hProcess);
        return false;
    }

    // 获取线程退出码（LoadLibraryW 的返回值）
    DWORD exitCode = 0;
    GetExitCodeThread(hThread, &exitCode);

    CloseHandle(hThread);
    VirtualFreeEx(hProcess, pRemotePath, 0, MEM_RELEASE);
    CloseHandle(hProcess);

    if (exitCode == 0) {
        LOG_ERROR("LoadLibraryW 返回 NULL，DLL 加载失败");
        return false;
    }

    LOG("DLL 注入成功，模块句柄: 0x%08X", exitCode);
    ctx->injected = true;
    return true;
}

bool Injector_IsInjected(InjectorContext* ctx) {
    if (!ctx) {
        return false;
    }

    // 如果之前标记为已注入，验证 DLL 是否仍然加载
    if (ctx->injected) {
        const wchar_t* dllName = GetFileName(ctx->dllPath);
        ctx->injected = IsDllLoaded(ctx->pid, dllName);
    }

    return ctx->injected;
}

bool Injector_EnsureInjection(InjectorContext* ctx) {
    if (!ctx) {
        return false;
    }

    // 检查进程是否存活
    if (!Injector_IsProcessAlive(ctx)) {
        LOG("目标进程已退出，需要重新查找进程");
        ctx->injected = false;
        return false;
    }

    // 检查 DLL 是否已注入
    if (Injector_IsInjected(ctx)) {
        return true;
    }

    // 重新注入
    LOG("DLL 未注入或已卸载，正在重新注入...");
    return Injector_Inject(ctx);
}

bool Injector_IsProcessAlive(InjectorContext* ctx) {
    if (!ctx || ctx->pid == 0) {
        return false;
    }

    HANDLE hProcess = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, ctx->pid);
    if (hProcess == NULL) {
        return false;
    }

    DWORD exitCode = 0;
    BOOL result = GetExitCodeProcess(hProcess, &exitCode);
    CloseHandle(hProcess);

    // STILL_ACTIVE (259) 表示进程仍在运行
    return result && exitCode == STILL_ACTIVE;
}

DWORD Injector_GetPid(InjectorContext* ctx) {
    return ctx ? ctx->pid : 0;
}

void Injector_SetPid(InjectorContext* ctx, DWORD pid) {
    if (ctx) {
        ctx->pid = pid;
        ctx->injected = false;  // 重置注入状态
    }
}

bool Injector_GetDefaultDllPath(wchar_t* buffer, size_t bufferSize) {
    if (!buffer || bufferSize == 0) {
        return false;
    }

    // 获取当前模块路径
    HMODULE hModule = NULL;
    // 获取当前 DLL/EXE 的句柄
    if (!GetModuleHandleExW(
            GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            (LPCWSTR)Injector_GetDefaultDllPath,
            &hModule)) {
        // 如果失败，使用 NULL 获取主模块
        hModule = NULL;
    }

    if (GetModuleFileNameW(hModule, buffer, (DWORD)bufferSize) == 0) {
        return false;
    }

    // 找到最后一个反斜杠
    wchar_t* lastSlash = wcsrchr(buffer, L'\\');
    if (lastSlash != NULL) {
        *(lastSlash + 1) = L'\0';
    }

    // 拼接 DLL 文件名
    wcscat_s(buffer, bufferSize, L"msa_hook.dll");

    return true;
}
