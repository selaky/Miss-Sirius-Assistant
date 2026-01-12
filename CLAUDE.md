# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

MSA (Miss.Sirius Assistant) 是基于 [MAA Framework](https://github.com/MaaXYZ/MaaFramework) 开发的《星纪元》游戏自动化脚本。主要功能包括自动跑图、自动战斗、自动补给。

## 常用命令

```bash
# Pipeline 配置检查（检测悬空引用、重复节点、缺失模板图片等）
  python my_tools/check_pipeline.py
  python my_tools/check_pipeline.py --strict 严格模式（有 WARN 也返回非 0）
  python my_tools/check_pipeline.py --no-unreachable 不提示“可能未触达的遗留节点”

# JSON/YAML 格式化（使用 prettier）
npx prettier --write "assets/**/*.json"
```

## 核心架构

### MAA Framework Pipeline 机制

执行逻辑
流程控制机制
任务触发

通过 tasker.post_task 接口指定入口节点启动任务
顺序检测

对当前节点的 next 列表进行顺序检测
依次尝试识别每个子节点配置的 recognition 特征
中断机制

当检测到某个子节点匹配成功时，立即终止后续节点检测
执行匹配节点的 action 定义的操作
后继处理

操作执行完成后，将激活节点切换为当前节点
重复执行上述检测流程
终止条件
当满足以下任意条件时，任务流程终止：

当前节点的 next 列表为空
所有后继节点持续检测失败直至超时

### 目录结构

```
assets/                          # 主要开发目录
├── interface.json               # UI 配置、任务入口、用户选项定义
├── resource/
│   ├── pipeline/                # 任务流水线 JSON 文件
│   │   ├── 跑图主流程.json      # 主入口流程
│   │   ├── 恢复.json            # 药品恢复逻辑
│   │   ├── 战斗.json            # 战斗流程
│   │   └── 意外处理.json        # 异常情况处理
│   └── image/                   # 模板匹配图片资源
│       ├── 跑图/
│       ├── 恢复/
│       ├── 战斗/
│       └── 意外/
agent/                           # Python 自定义识别和动作
├── main.py                      # Agent 入口
├── recover/                     # 恢复相关模块
│   ├── recover_action.py        # 恢复相关自定义动作
│   ├── recover_reco.py          # 恢复相关自定义识别
│   └── recover_helper.py        # 药品状态管理
└── arena/                       # 竞技场相关模块
deps/                            # MAA Framework SDK 和文档
└── docs/zh_cn/                  # 中文文档（Pipeline 协议、接口说明等）
tools/                           # 构建和检查工具
├── install.py                   # 打包脚本（生成构建产物到 install/）
└── configure.py                 # OCR 模型配置

# 注意：install/ 是 CI 构建时动态生成的产物目录，已在 .gitignore 中忽略
# 开发时不应参考或依赖该目录中的任何内容
```

### 关键配置文件

**interface.json** - 定义 UI 和任务：

- `task`: 任务列表，每个任务有 `entry`（入口节点）和 `option`（用户选项）
- `option`: 用户可配置选项，通过 `pipeline_override` 动态修改节点属性
- `controller`: 控制器配置（Win32 桌面端）

**Pipeline JSON** - 节点定义示例：

```jsonc
{
    "节点名": {
        "recognition": {
            "type": "TemplateMatch",
            "param": {
                "template": ["路径/图片.png"],
                "roi": [x, y, w, h]  // 识别区域
            }
        },
        "action": {
            "type": "Click"
        },
        "next": ["下一节点A", "下一节点B"]
    }
}
```

### Python Agent

Agent 通过 `maa.agent.agent_server` 实现自定义识别和动作：

```python
from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction

@AgentServer.custom_action("action_name")
class MyAction(CustomAction):
    def run(self, context, argv) -> bool:
        # 实现自定义逻辑
        return True
```

## 开发注意事项

- Pipeline JSON 支持 JSONC 注释（`//` 和 `/* */`）
- 节点名不能以 `$` 开头（保留给编辑器元数据）
- 模板图片路径相对于 `assets/resource/image/`
- `pipeline_override` 可在 interface.json 中动态覆盖节点属性
- 使用 `jump_back: true` 实现循环流程

## 相关文档

- MAA Framework Pipeline 协议: `deps/docs/zh_cn/3.1-任务流水线协议.md`
- ProjectInterface 协议: `deps/docs/zh_cn/3.3-ProjectInterfaceV2协议.md`
- 控制方式说明: `deps/docs/zh_cn/2.4-控制方式说明.md`
