from __future__ import annotations

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context

from recover_state import POTION_KEYS, get_state, parse_custom_param_json, reset_state


@AgentServer.custom_action("msa_potion_reset_state")
class ResetPotionStateAction(CustomAction):
    """重置本次跑图任务中的“已吃药数量”计数。"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        reset_state(argv.task_detail.task_id)
        return True


@AgentServer.custom_action("msa_potion_increment_used")
class IncrementPotionUsedAction(CustomAction):
    """在判定“要使用某瓶药”时，把对应的已使用数量 +1。

    所需参数（custom_action_param，JSON）：
    - potion_key: "ap_big" | "ap_small" | "bc_big" | "bc_small"
    """

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        param = parse_custom_param_json(
            argv.custom_action_param,
            where=f"CustomAction({argv.custom_action_name})@{argv.node_name}",
        )
        if not isinstance(param, dict):
            raise TypeError(
                f"{argv.node_name} custom_action_param 期望为 JSON 对象(dict)，但拿到：{param!r}"
            )

        potion_key = param.get("potion_key")
        if potion_key not in POTION_KEYS:
            raise ValueError(
                f"{argv.node_name} potion_key 非法：{potion_key!r}，允许值={POTION_KEYS}"
            )

        state = get_state(argv.task_detail.task_id)
        state.used_count[potion_key] += 1

        return True
