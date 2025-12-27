# 🎓 自定义动作（Custom Action）新手学习指南

## 📖 目录
1. [什么是自定义动作](#什么是自定义动作)
2. [代码结构详解](#代码结构详解)
3. [核心知识点](#核心知识点)
4. [如何使用](#如何使用)
5. [常见问题](#常见问题)

---

## 🎯 什么是自定义动作

### 简单理解
想象你在玩一个需要自动化的游戏：
- **JSON 配置文件**：就像一份菜单，列出了一系列简单的动作（点击、识别文字等）
- **自定义动作（Custom Action）**：就像你自己编写的特殊菜谱，可以实现复杂的逻辑

### 工作流程
```
用户启动任务
  ↓
读取 JSON 配置
  ↓
遇到自定义动作节点
  ↓
调用你的 Python 代码
  ↓
执行复杂逻辑
  ↓
返回结果继续执行
```

---

## 📝 代码结构详解

### 第 1 部分：导入必要的模块

```python
import json  # 用于处理 JSON 数据
from maa.agent.agent_server import AgentServer  # 用于注册自定义动作
from maa.custom_action import CustomAction      # 自定义动作的基类
from maa.context import Context                 # 上下文，包含游戏画面、控制器等
from states import potion_stats                 # 我们自己的药水管理模块
```

**知识点：什么是 import？**
- `import` 就像去图书馆借书，把别人写好的代码拿来用
- 你不需要重新造轮子，直接使用已有的功能即可

---

### 第 2 部分：定义自定义动作类

```python
@AgentServer.custom_action("init_potion_data")  # ← 这是装饰器，给动作起名
class InitPotionData(CustomAction):             # ← 定义一个类，继承 CustomAction
    """Initialize potion usage data"""          # ← 这是注释，描述这个类的作用

    def run(self, context, argv) -> bool:       # ← 必须实现的方法
        # 你的代码逻辑
        return True  # 返回 True 表示成功
```

**知识点解析：**

#### 1. 装饰器（Decorator）`@`
```python
@AgentServer.custom_action("init_potion_data")
```
- **作用**：告诉 MaaFramework "我有一个自定义动作叫 `init_potion_data`"
- **类比**：就像给你的函数贴了一个标签，方便 JSON 配置文件调用
- **重要**：括号里的名字 `"init_potion_data"` 要和 JSON 配置文件中的 `custom_action` 字段一致

#### 2. 类（Class）
```python
class InitPotionData(CustomAction):
```
- **作用**：把相关的代码组织在一起
- **继承**：`(CustomAction)` 表示继承基类，获得基础功能
- **命名**：类名通常用大驼峰命名（每个单词首字母大写）

#### 3. run 方法
```python
def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
```
- **self**：指向当前对象本身（Python 类方法的第一个参数）
- **context**：包含游戏画面、控制器等信息的上下文对象
- **argv**：包含从 JSON 传过来的参数
- **-> bool**：表示这个方法返回一个布尔值（True 或 False）

---

### 第 3 部分：获取用户参数

```python
# 从 JSON 配置传来的参数中获取值
try:
    if argv.custom_action_param:  # 检查参数是否存在
        params = json.loads(argv.custom_action_param)  # 解析 JSON 字符串
        small_limit = params.get("small_ap_limit", 60)  # 获取值，默认 60
        big_limit = params.get("big_ap_limit", 999)     # 获取值，默认 999
    else:
        small_limit = 60
        big_limit = 999
except Exception as e:
    print(f"参数解析失败：{e}")
    small_limit = 60
    big_limit = 999
```

**关键知识点：**

#### 1. `argv.custom_action_param` 是字符串！
```python
# ❌ 错误写法（会报错）
value = argv.custom_action_param['big_ap']

# ✅ 正确写法
params = json.loads(argv.custom_action_param)  # 先转换成字典
value = params.get('big_ap')                    # 再获取值
```

#### 2. `try-except` 异常处理
- **try**：尝试执行代码
- **except**：如果出错了，执行这里的代码
- **作用**：避免程序崩溃，提供默认值

#### 3. `dict.get(key, default)` 方法
```python
small_limit = params.get("small_ap_limit", 60)
```
- 如果 `params` 字典中有 `"small_ap_limit"` 键，返回对应的值
- 如果没有，返回默认值 `60`
- **好处**：比直接用 `params["small_ap_limit"]` 更安全，不会因为键不存在而报错

---

### 第 4 部分：业务逻辑

```python
if potion_stats.ap.small.usage < small_limit:
    # 小药还没用完，使用小药
    potion_stats.ap.small.inc_usage()
    print(f"使用小 AP 药（已用 {potion_stats.ap.small.usage}/{small_limit}）")
    return True

elif potion_stats.ap.big.usage < big_limit:
    # 小药用完了，使用大药
    potion_stats.ap.big.inc_usage()
    print(f"使用大 AP 药（已用 {potion_stats.ap.big.usage}/{big_limit}）")
    return True

else:
    # 两种药都用完了
    print("⚠️ AP 药水已经用完！")
    return False
```

**知识点：if-elif-else 条件判断**
- **if**：如果条件成立，执行这里
- **elif**：否则如果（else if 的缩写）
- **else**：以上条件都不成立时执行

**知识点：f-string 格式化字符串**
```python
print(f"已用 {potion_stats.ap.small.usage}/{small_limit}")
```
- `f` 开头的字符串可以在 `{}` 中嵌入变量
- 输出示例：`已用 5/60`

---

## 🔧 核心知识点总结

### 1. Python 基础语法

| 概念 | 说明 | 示例 |
|-----|------|------|
| **变量** | 存储数据的容器 | `limit = 60` |
| **函数** | 可重复使用的代码块 | `def run():` |
| **类** | 把相关功能组织在一起 | `class MyAction:` |
| **条件判断** | 根据条件执行不同代码 | `if x > 10:` |
| **异常处理** | 处理错误情况 | `try: ... except:` |

### 2. MaaFramework 特有概念

| 概念 | 说明 | 用途 |
|-----|------|------|
| **装饰器** | `@AgentServer.custom_action()` | 注册自定义动作 |
| **Context** | 上下文对象 | 访问游戏画面、控制器 |
| **argv** | 参数对象 | 获取配置参数 |
| **返回值** | `True/False` | 告诉框架执行成功或失败 |

### 3. 数据类型

```python
# 整数（int）
age = 25

# 字符串（str）
name = "Claude"

# 布尔值（bool）
is_success = True

# 字典（dict）
person = {"name": "Claude", "age": 25}

# 列表（list）
numbers = [1, 2, 3, 4, 5]
```

---

## 🚀 如何使用

### 步骤 1：确保 agent/main.py 加载了这个模块

检查 `agent/main.py` 文件，确保导入了 `recover_action`：

```python
# agent/main.py
import recover_action  # 导入我们的自定义动作模块
import my_action
import my_reco
```

### 步骤 2：在 JSON 配置文件中调用

在你的 pipeline JSON 文件中使用自定义动作：

```json
{
    "初始化药水数据": {
        "action": {
            "type": "Custom",
            "param": {
                "custom_action": "init_potion_data"
            }
        },
        "next": ["下一个任务"]
    },

    "使用AP药水": {
        "action": {
            "type": "Custom",
            "param": {
                "custom_action": "use_ap_potion",
                "custom_action_param": "{\"small_ap_limit\": 60, \"big_ap_limit\": 999}"
            }
        }
    }
}
```

### 步骤 3：运行测试

运行你的 MaaFramework 项目，观察控制台输出，检查是否正确执行。

---

## ❓ 常见问题

### Q1: 为什么 `argv.custom_action_param` 需要用 `json.loads()` 解析？

**A:** MaaFramework 将参数作为 JSON 字符串传递，例如：
```python
# argv.custom_action_param 的值是字符串：
'{"small_ap_limit": 60, "big_ap_limit": 999}'

# 你需要先转换成 Python 字典：
params = json.loads(argv.custom_action_param)
# 现在 params 是字典：
{'small_ap_limit': 60, 'big_ap_limit': 999}
```

### Q2: `return True` 和 `return False` 有什么区别？

**A:**
- `return True`：告诉 MaaFramework 这个动作**执行成功**，继续执行后续任务
- `return False`：告诉 MaaFramework 这个动作**执行失败**，可能会触发错误处理流程

### Q3: 如何在自定义动作中点击屏幕？

**A:** 使用 `context.controller`：
```python
def run(self, context, argv):
    # 点击坐标 (100, 200)
    context.controller.post_click(100, 200).wait()

    # 滑动
    context.controller.post_swipe(100, 100, 200, 200, 500).wait()

    return True
```

### Q4: 如何调试我的代码？

**A:** 使用 `print()` 输出调试信息：
```python
print(f"调试：small_limit = {small_limit}")
print(f"调试：当前使用量 = {potion_stats.ap.small.usage}")
```

### Q5: 类名和装饰器里的名字要一样吗？

**A:** 不需要！
- **类名**（如 `InitPotionData`）：只在 Python 代码内部使用
- **装饰器名字**（如 `"init_potion_data"`）：在 JSON 配置文件中使用

JSON 配置通过装饰器里的名字来找到对应的类。

---

## 🎯 下一步学习

1. **实践**：修改代码，添加自己的逻辑
2. **阅读文档**：查看项目中的 `docs/override.md` 了解参数传递
3. **参考示例**：查看 `agent/my_action.py` 学习其他用法
4. **尝试调试**：运行代码，观察输出，理解执行流程

---

## 📚 相关资源

- [MaaFramework 官方文档](https://github.com/MaaXYZ/MaaFramework)
- [Python 基础教程](https://www.runoob.com/python3/python3-tutorial.html)
- [JSON 格式说明](https://www.json.org/json-zh.html)

---

**祝你学习愉快！有问题随时问我！** 🎉
