from __future__ import annotations

from typing import Any

from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context

from recover_state import (
    POTION_KEYS,
    coerce_int,
    get_state,
    parse_custom_param_json,
    read_ocr_int_from_node,
)


@AgentServer.custom_recognition("msa_potion_can_use")
class PotionCanUseRecognition(CustomRecognition):
    """判断某一瓶恢复药在当前恢复界面是否“允许使用”。

    规则：
    - 用户设置的使用上限为 0：不使用（直接返回 false）
    - 用户设置的使用上限为 -1：无限使用（只受“剩余数量”限制）
    - 其余正整数：已使用数量 < 上限 且 剩余数量 != 0 才允许

    所需参数（custom_recognition_param，JSON）：
    - potion_key: "ap_big" | "ap_small" | "bc_big" | "bc_small"
    - count_node: OCR 统计节点名（例如："统计大AP药数量"）
    - max_use: int（由 UI 输入注入；注意要做字符串→数字转换）
    """

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        param = parse_custom_param_json(
            argv.custom_recognition_param,
            where=f"CustomRecognition({argv.custom_recognition_name})@{argv.node_name}",
        )
        if not isinstance(param, dict):
            raise TypeError(
                f"{argv.node_name} custom_recognition_param 期望为 JSON 对象(dict)，但拿到：{param!r}"
            )

        potion_key = param.get("potion_key")
        if potion_key not in POTION_KEYS:
            raise ValueError(
                f"{argv.node_name} potion_key 非法：{potion_key!r}，允许值={POTION_KEYS}"
            )

        count_node = param.get("count_node")
        if not isinstance(count_node, str) or not count_node.strip():
            raise ValueError(f"{argv.node_name} count_node 非法：{count_node!r}")

        max_use = coerce_int(param.get("max_use"), where=f"{argv.node_name}.max_use")

        remaining = read_ocr_int_from_node(argv.task_detail, node_name=count_node)
        used = get_state(argv.task_detail.task_id).used_count[potion_key]

        can_use = (
            remaining != 0
            and max_use != 0
            and (max_use == -1 or used < max_use)
        )

        detail: dict[str, Any] = {
            "potion_key": potion_key,
            "count_node": count_node,
            "remaining": remaining,
            "used": used,
            "max_use": max_use,
            "can_use": can_use,
        }

        if not can_use:
            return CustomRecognition.AnalyzeResult(box=None, detail=detail)

        # 命中时返回一个 box（这里用 ROI 自身即可），用于让框架判定 hit。
        return CustomRecognition.AnalyzeResult(box=tuple(argv.roi), detail=detail)
