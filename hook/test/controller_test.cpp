/**
 * MSA 后台控制器完整功能测试程序
 *
 * 第三阶段验收测试
 *
 * 功能：
 * 1. 使用自定义控制器连接游戏（自动注入 Hook DLL）
 * 2. 通过 MAA API 执行后台截图
 * 3. 通过 MAA API 执行后台点击
 * 4. 通过 MAA API 执行后台滑动
 * 5. 测试游戏重启后自动重新注入
 *
 * 验收标准：
 * - 游戏窗口可以在后台（被其他窗口遮挡）
 * - 截图成功并保存为文件
 * - 点击能够触发游戏响应
 * - 滑动能够触发游戏响应
 * - 游戏重启后，控制器能自动重新注入并继续工作
 */

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#include "controller/controller.h"
#include "MaaFramework/MaaAPI.h"

// 日志输出
void Log(const char* format, ...) {
    // 获取当前时间
    time_t now = time(NULL);
    struct tm* t = localtime(&now);

    printf("[%02d:%02d:%02d] ", t->tm_hour, t->tm_min, t->tm_sec);

    va_list args;
    va_start(args, format);
    vprintf(format, args);
    va_end(args);

    printf("\n");
}

void LogError(const char* format, ...) {
    time_t now = time(NULL);
    struct tm* t = localtime(&now);

    printf("[%02d:%02d:%02d] [错误] ", t->tm_hour, t->tm_min, t->tm_sec);

    va_list args;
    va_start(args, format);
    vprintf(format, args);
    va_end(args);

    printf(" (错误码: %lu)\n", GetLastError());
}

void LogSuccess(const char* format, ...) {
    time_t now = time(NULL);
    struct tm* t = localtime(&now);

    printf("[%02d:%02d:%02d] [成功] ", t->tm_hour, t->tm_min, t->tm_sec);

    va_list args;
    va_start(args, format);
    vprintf(format, args);
    va_end(args);

    printf("\n");
}

// 保存 BGRA 数据为 BMP 文件
bool SaveBMP(const char* filename, const uint8_t* data, int width, int height) {
    #pragma pack(push, 1)
    struct BMPFileHeader {
        uint16_t type;
        uint32_t size;
        uint16_t reserved1;
        uint16_t reserved2;
        uint32_t offset;
    };

    struct BMPInfoHeader {
        uint32_t size;
        int32_t width;
        int32_t height;
        uint16_t planes;
        uint16_t bitCount;
        uint32_t compression;
        uint32_t sizeImage;
        int32_t xPelsPerMeter;
        int32_t yPelsPerMeter;
        uint32_t clrUsed;
        uint32_t clrImportant;
    };
    #pragma pack(pop)

    FILE* fp = fopen(filename, "wb");
    if (!fp) {
        return false;
    }

    int rowSize = ((width * 4 + 3) / 4) * 4;
    int imageSize = rowSize * height;

    BMPFileHeader fileHeader = {};
    fileHeader.type = 0x4D42;
    fileHeader.size = sizeof(BMPFileHeader) + sizeof(BMPInfoHeader) + imageSize;
    fileHeader.offset = sizeof(BMPFileHeader) + sizeof(BMPInfoHeader);

    BMPInfoHeader infoHeader = {};
    infoHeader.size = sizeof(BMPInfoHeader);
    infoHeader.width = width;
    infoHeader.height = -height;
    infoHeader.planes = 1;
    infoHeader.bitCount = 32;
    infoHeader.compression = 0;
    infoHeader.sizeImage = imageSize;

    fwrite(&fileHeader, sizeof(fileHeader), 1, fp);
    fwrite(&infoHeader, sizeof(infoHeader), 1, fp);

    for (int y = 0; y < height; ++y) {
        fwrite(data + y * width * 4, width * 4, 1, fp);
        int padding = rowSize - width * 4;
        if (padding > 0) {
            uint8_t zeros[4] = {0};
            fwrite(zeros, padding, 1, fp);
        }
    }

    fclose(fp);
    return true;
}

// 事件回调
void EventCallback(void* handle, const char* message, const char* details_json, void* trans_arg) {
    // 只打印重要事件
    if (strstr(message, "Error") || strstr(message, "Failed")) {
        Log("MAA 事件: %s", message);
    }
}

// 执行截图测试
bool TestScreencap(MaaController* controller) {
    Log("正在执行截图测试...");

    MaaCtrlId screencapId = MaaControllerPostScreencap(controller);
    MaaStatus status = MaaControllerWait(controller, screencapId);

    if (status != MaaStatus_Succeeded) {
        LogError("截图失败，状态: %d", status);
        return false;
    }

    MaaImageBuffer* imageBuffer = MaaImageBufferCreate();
    if (!MaaControllerCachedImage(controller, imageBuffer)) {
        LogError("获取截图数据失败");
        MaaImageBufferDestroy(imageBuffer);
        return false;
    }

    int width = MaaImageBufferWidth(imageBuffer);
    int height = MaaImageBufferHeight(imageBuffer);
    void* rawData = MaaImageBufferGetRawData(imageBuffer);

    // 生成文件名
    time_t now = time(NULL);
    struct tm* t = localtime(&now);
    char filename[256];
    snprintf(filename, sizeof(filename), "test_screenshot_%02d%02d%02d.bmp",
        t->tm_hour, t->tm_min, t->tm_sec);

    if (SaveBMP(filename, (const uint8_t*)rawData, width, height)) {
        LogSuccess("截图成功！尺寸: %d x %d，已保存: %s", width, height, filename);
    } else {
        LogError("保存截图失败");
        MaaImageBufferDestroy(imageBuffer);
        return false;
    }

    MaaImageBufferDestroy(imageBuffer);
    return true;
}

// 执行点击测试
bool TestClick(MaaController* controller, int x, int y) {
    Log("正在执行点击测试: (%d, %d)...", x, y);

    MaaCtrlId clickId = MaaControllerPostClick(controller, x, y);
    MaaStatus status = MaaControllerWait(controller, clickId);

    if (status != MaaStatus_Succeeded) {
        LogError("点击失败，状态: %d", status);
        return false;
    }

    LogSuccess("点击成功！坐标: (%d, %d)", x, y);
    return true;
}

// 执行滑动测试
bool TestSwipe(MaaController* controller, int x1, int y1, int x2, int y2, int duration) {
    Log("正在执行滑动测试: (%d, %d) -> (%d, %d), 时长: %d ms...", x1, y1, x2, y2, duration);

    MaaCtrlId swipeId = MaaControllerPostSwipe(controller, x1, y1, x2, y2, duration);
    MaaStatus status = MaaControllerWait(controller, swipeId);

    if (status != MaaStatus_Succeeded) {
        LogError("滑动失败，状态: %d", status);
        return false;
    }

    LogSuccess("滑动成功！");
    return true;
}

// 打印菜单
void PrintMenu() {
    printf("\n");
    printf("========================================\n");
    printf("    MSA 后台控制器测试菜单\n");
    printf("========================================\n");
    printf("1. 截图测试（保存为 BMP 文件）\n");
    printf("2. 点击窗口中心\n");
    printf("3. 点击指定坐标\n");
    printf("4. 滑动测试（从中心向下滑动）\n");
    printf("5. 滑动指定坐标\n");
    printf("6. 连续操作测试（截图+点击+截图）\n");
    printf("7. 重新注入测试（请先重启游戏）\n");
    printf("0. 退出\n");
    printf("========================================\n");
}

int main() {
    // 设置控制台编码为 UTF-8
    SetConsoleOutputCP(65001);

    printf("========================================\n");
    printf("    MSA 后台控制器完整功能测试\n");
    printf("    第三阶段验收\n");
    printf("========================================\n\n");

    Log("正在初始化...");

    // 创建控制器上下文
    Log("创建控制器...");
    MsaControllerContext* ctx = MsaController_Create(NULL);
    if (!ctx) {
        LogError("创建控制器上下文失败");
        printf("\n按任意键退出...");
        getchar();
        return 1;
    }

    // 创建 MAA 控制器
    MaaController* controller = MaaCustomControllerCreate(
        MsaController_GetCallbacks(ctx),
        MsaController_GetTransArg(ctx)
    );

    if (!controller) {
        LogError("创建 MAA 控制器失败");
        MsaController_Destroy(ctx);
        printf("\n按任意键退出...");
        getchar();
        return 1;
    }

    // 添加事件回调
    MaaControllerAddSink(controller, EventCallback, NULL);

    // 连接（包含自动注入）
    Log("正在连接游戏（包含自动注入 Hook DLL）...");
    MaaCtrlId connId = MaaControllerPostConnection(controller);
    MaaStatus status = MaaControllerWait(controller, connId);

    if (status != MaaStatus_Succeeded) {
        LogError("连接失败，状态: %d", status);
        MaaControllerDestroy(controller);
        MsaController_Destroy(ctx);
        printf("\n按任意键退出...");
        getchar();
        return 1;
    }

    LogSuccess("连接成功！Hook DLL 已自动注入");

    // 获取 UUID
    MaaStringBuffer* uuidBuffer = MaaStringBufferCreate();
    if (MaaControllerGetUuid(controller, uuidBuffer)) {
        Log("控制器 UUID: %s", MaaStringBufferGet(uuidBuffer));
    }
    MaaStringBufferDestroy(uuidBuffer);

    // 获取窗口大小（通过截图）
    int windowWidth = 1280;
    int windowHeight = 720;

    MaaCtrlId screencapId = MaaControllerPostScreencap(controller);
    if (MaaControllerWait(controller, screencapId) == MaaStatus_Succeeded) {
        MaaImageBuffer* imageBuffer = MaaImageBufferCreate();
        if (MaaControllerCachedImage(controller, imageBuffer)) {
            windowWidth = MaaImageBufferWidth(imageBuffer);
            windowHeight = MaaImageBufferHeight(imageBuffer);
            Log("检测到窗口大小: %d x %d", windowWidth, windowHeight);
        }
        MaaImageBufferDestroy(imageBuffer);
    }

    // 交互式测试
    while (1) {
        PrintMenu();
        printf("\n请选择操作 (0-7): ");

        int choice;
        if (scanf("%d", &choice) != 1) {
            while (getchar() != '\n');
            continue;
        }

        switch (choice) {
        case 0:
            goto cleanup;

        case 1:
            // 截图测试
            TestScreencap(controller);
            break;

        case 2: {
            // 点击窗口中心
            int centerX = windowWidth / 2;
            int centerY = windowHeight / 2;
            TestClick(controller, centerX, centerY);
            break;
        }

        case 3: {
            // 点击指定坐标
            int x, y;
            printf("请输入 X 坐标: ");
            scanf("%d", &x);
            printf("请输入 Y 坐标: ");
            scanf("%d", &y);
            TestClick(controller, x, y);
            break;
        }

        case 4: {
            // 滑动测试（从中心向下滑动）
            int centerX = windowWidth / 2;
            int centerY = windowHeight / 2;
            int endY = centerY + 200;
            if (endY > windowHeight - 50) endY = windowHeight - 50;
            TestSwipe(controller, centerX, centerY, centerX, endY, 500);
            break;
        }

        case 5: {
            // 滑动指定坐标
            int x1, y1, x2, y2, duration;
            printf("请输入起点 X: ");
            scanf("%d", &x1);
            printf("请输入起点 Y: ");
            scanf("%d", &y1);
            printf("请输入终点 X: ");
            scanf("%d", &x2);
            printf("请输入终点 Y: ");
            scanf("%d", &y2);
            printf("请输入时长(ms): ");
            scanf("%d", &duration);
            TestSwipe(controller, x1, y1, x2, y2, duration);
            break;
        }

        case 6: {
            // 连续操作测试
            Log("开始连续操作测试...");

            Log("步骤 1/3: 截图");
            if (!TestScreencap(controller)) {
                LogError("连续测试失败：截图失败");
                break;
            }

            Sleep(500);

            Log("步骤 2/3: 点击窗口中心");
            int centerX = windowWidth / 2;
            int centerY = windowHeight / 2;
            if (!TestClick(controller, centerX, centerY)) {
                LogError("连续测试失败：点击失败");
                break;
            }

            Sleep(500);

            Log("步骤 3/3: 再次截图");
            if (!TestScreencap(controller)) {
                LogError("连续测试失败：第二次截图失败");
                break;
            }

            LogSuccess("连续操作测试完成！");
            break;
        }

        case 7: {
            // 重新注入测试
            Log("重新注入测试说明：");
            Log("1. 请先关闭游戏");
            Log("2. 重新启动游戏");
            Log("3. 按回车键继续测试");
            printf("\n按回车键继续...");
            while (getchar() != '\n');
            getchar();

            Log("正在尝试执行点击（将触发自动重新注入）...");
            int centerX = windowWidth / 2;
            int centerY = windowHeight / 2;

            if (TestClick(controller, centerX, centerY)) {
                LogSuccess("重新注入测试成功！控制器已自动重新注入");
            } else {
                LogError("重新注入测试失败");
                Log("提示：如果游戏进程已变化，可能需要重新连接控制器");
            }
            break;
        }

        default:
            printf("无效选择，请重试\n");
            break;
        }
    }

cleanup:
    // 清理
    Log("正在清理...");
    MaaControllerDestroy(controller);
    MsaController_Destroy(ctx);

    LogSuccess("测试程序结束");
    printf("\n按任意键退出...");
    getchar();
    getchar();

    return 0;
}
