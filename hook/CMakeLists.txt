# MSA 后台点击模块 CMake 配置
cmake_minimum_required(VERSION 3.15)

project(msa_hook LANGUAGES C CXX)

# 设置 C++ 标准
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Windows 特定设置
if(WIN32)
    # 设置 MSVC 编码为 UTF-8
    add_compile_options("$<$<CXX_COMPILER_ID:MSVC>:/utf-8>")
    add_compile_options("$<$<C_COMPILER_ID:MSVC>:/utf-8>")

    # 定义 Windows 版本（Windows 10 1903+，支持 Windows Graphics Capture）
    add_definitions(-D_WIN32_WINNT=0x0A00)
    add_definitions(-DWINVER=0x0A00)
    add_definitions(-DUNICODE -D_UNICODE)

    # C++/WinRT 编译选项（C++20 默认支持协程，不需要 /await）
endif()

# MAA Framework 路径
set(MAA_FRAMEWORK_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../deps")

# 添加 MinHook 子项目
add_subdirectory(third_party/minhook)

# ==================== Hook DLL ====================
set(HOOK_DLL_SOURCES
    dll/dllmain.cpp
    dll/hooks.cpp
    dll/shared_memory.cpp
)

add_library(msa_hook SHARED ${HOOK_DLL_SOURCES})

target_include_directories(msa_hook PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/common
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/minhook/include
)

target_link_libraries(msa_hook PRIVATE minhook)

# 设置 DLL 输出名称
set_target_properties(msa_hook PROPERTIES
    OUTPUT_NAME "msa_hook"
    PREFIX ""
)

# ==================== 自定义控制器静态库 ====================
set(CONTROLLER_SOURCES
    controller/controller.cpp
    controller/shared_memory.cpp
    controller/screencap.cpp
    controller/injector.cpp
)

add_library(msa_controller STATIC ${CONTROLLER_SOURCES})

target_include_directories(msa_controller PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/common
    ${MAA_FRAMEWORK_DIR}/include
)

# 链接 MAA Framework 和 Windows 库
target_link_libraries(msa_controller PUBLIC
    ${MAA_FRAMEWORK_DIR}/lib/MaaFramework.lib
    d3d11
    dxgi
    user32
    kernel32
)

# C++/WinRT 需要链接 windowsapp.lib
target_link_libraries(msa_controller PUBLIC windowsapp)

# ==================== 第一阶段测试程序（点击测试） ====================
set(TEST_SOURCES
    test/click_test.cpp
)

add_executable(click_test ${TEST_SOURCES})

target_include_directories(click_test PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/common
)

# 链接 Windows 库
target_link_libraries(click_test PRIVATE user32 kernel32)

# 设置测试程序为 Windows 控制台应用
set_target_properties(click_test PROPERTIES
    WIN32_EXECUTABLE FALSE
)

# ==================== 第二阶段测试程序（截图测试） ====================
set(SCREENCAP_TEST_SOURCES
    test/screencap_test.cpp
)

add_executable(screencap_test ${SCREENCAP_TEST_SOURCES})

target_include_directories(screencap_test PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/common
    ${MAA_FRAMEWORK_DIR}/include
)

# 链接控制器库和 MAA Framework
target_link_libraries(screencap_test PRIVATE
    msa_controller
    ${MAA_FRAMEWORK_DIR}/lib/MaaFramework.lib
    user32
    kernel32
)

# 设置测试程序为 Windows 控制台应用
set_target_properties(screencap_test PROPERTIES
    WIN32_EXECUTABLE FALSE
)

# ==================== 安装配置 ====================
# 将 DLL 和测试程序输出到同一目录
set_target_properties(msa_hook msa_controller click_test screencap_test PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib"
)

# ==================== 第三阶段测试程序（完整功能测试） ====================
set(CONTROLLER_TEST_SOURCES
    test/controller_test.cpp
)

add_executable(controller_test ${CONTROLLER_TEST_SOURCES})

target_include_directories(controller_test PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/common
    ${MAA_FRAMEWORK_DIR}/include
)

# 链接控制器库和 MAA Framework
target_link_libraries(controller_test PRIVATE
    msa_controller
    ${MAA_FRAMEWORK_DIR}/lib/MaaFramework.lib
    user32
    kernel32
)

# 设置测试程序为 Windows 控制台应用
set_target_properties(controller_test PROPERTIES
    WIN32_EXECUTABLE FALSE
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)

# 安装目标
install(TARGETS msa_hook msa_controller click_test screencap_test controller_test
    RUNTIME DESTINATION bin
    LIBRARY DESTINATION bin
    ARCHIVE DESTINATION lib
)

# 复制 MAA Framework DLL 到输出目录
add_custom_command(TARGET controller_test POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "${MAA_FRAMEWORK_DIR}/bin/MaaFramework.dll"
        "$<TARGET_FILE_DIR:controller_test>"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "${MAA_FRAMEWORK_DIR}/bin/MaaToolkit.dll"
        "$<TARGET_FILE_DIR:controller_test>"
    COMMENT "Copying MAA Framework DLLs..."
)
