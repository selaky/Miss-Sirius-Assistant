# **开发指南：如何将 Interface 输入框数据稳定传入 Python**

## **1. 核心结论**

- **GUI 输入框的值不会自动成为 Python 变量。**
- GUI 界面上的输入框（`interface.json` 中的 `input`）的作用是，根据用户输入生成一个 **`pipeline_override`（流程配置补丁）**。
- Python 自定义代码能获取到的“用户配置”，其稳定来源只有一个：**当前节点的 `custom_action_param` 或 `custom_recognition_param`**。

**简而言之：**
要在 Python 中使用用户输入的值（例如“大小 AP/BC 上限”），就必须通过 `pipeline_override` 将这些值写入目标节点的 `custom_*_param` 中，然后 Python 代码再从该参数中读取。

## **2. 关键发现与原理（重要）**

**发现 A：`custom_*_param` 在 Python 中是 JSON 字符串，不是字典**

- 框架传递给自定义动作/识别的 `argv.custom_action_param` 和 `argv.custom_recognition_param` 是一个完整的 JSON 字符串，例如：`'{"big_ap":999, "small_ap":60}'`。
- **正确用法：** 必须先使用 `json.loads()` 将该字符串解析为 Python 字典后才能使用，否则会直接报错。

```python
import json

# 错误用法：
# value = argv.custom_action_param['big_ap'] # 这会报错

# 正确用法：
params = json.loads(argv.custom_action_param)
value = params.get('big_ap')
```

**发现 B：`pipeline_override` 是“整体替换”，而非“增量合并”**

- 当 `pipeline_override` 修改一个节点的 `custom_*_param` 时，它会用新的值**完全覆盖**掉 `pipeline.json` 中预设的旧值。
- **正确用法：** 如果需要传递多个值（如 4 个上限值），`pipeline_override` 必须一次性提供所有值。不要期望只更新其中一个值，而其他值会自动保留。

**发现 C：必须使用 v2 版本的 Pipeline 结构**

项目中的 `pipeline.json` 文件使用的是 v2 格式，节点结构如下：

```json
"action": {
  "type": "Custom",
  "param": {
    "custom_action": "YourActionName",
    "custom_action_param": "{...}" // 注意这里的值是字符串
  }
}
```

`pipeline_override` 的路径也应遵循此结构，例如：`节点名.action.param.custom_action_param`。若使用 v1 版本的旧写法，将导致参数无法被正确读取。

## **3. 推荐实施方案**

将用户输入的 4 个值（大小 AP/BC 上限）注入到 **`初始化吃药数据`** 节点中。

**具体步骤：**

1. **修改 Pipeline 节点：**
    将 `跑图主流程.json` 文件中的 `初始化吃药数据` 节点改造为一个自定义动作（Custom Action）节点，并定义好 `custom_action` 的名称。

2. **配置 Interface 模板：**
    在 `interface.json` 中，为 `恢复药使用上限` 这个 `input` 选项配置 `pipeline_override` 模板。

3. **生成 Override 内容：**
    模板应将 4 个输入框的值组合成一个 JSON 字符串，并将其写入 `初始化吃药数据.action.param.custom_action_param`。

4. **Python 代码读取：**
    在 `初始化吃药数据` 对应的自定义动作 Python 代码中，通过 `argv.custom_action_param` 获取该 JSON 字符串，使用 `json.loads()` 解析后即可获得这 4 个值。

## **4. 常见问题与避坑指南**

1. **【高危】直接将 `custom_*_param` 当作字典使用**
    - **后果：** 代码直接报错。
    - **解决：** 永远记得先用 `json.loads()` 解析。

2. **【高危】`pipeline_override` 只传递部分字段**
    - **后果：** 未被传递的字段会丢失（因为是整体替换）。
    - **解决：** 确保 `override` 中包含所有需要用到的字段。

3. **【中危】混用 v1 和 v2 的 Pipeline 写法**
    - **后果：** 节点不生效或参数读取不到。
    - **解决：** 统一使用 v2 结构（`action: { "type": ..., "param": ... }`）。

4. **【中危】`override` 路径错误，覆盖了整个 `param` 对象**
    - **后果：** 可能导致 `custom_action` 的名称被抹掉，使节点失效。
    - **解决：** `override` 的路径应精确到要修改的参数，例如：`节点名.action.param.custom_action_param`。

---
