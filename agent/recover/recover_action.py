# input: recover_manager
# output: 暂无
# pos: 这里是恢复流程中执行的动作

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from . import recover_manager
import logging
import json
from utils import common_func


@AgentServer.custom_action("reset_potion_data")
class ResetPotionData(CustomAction):
    """重置药水数据"""
    def run(self,context:Context,argv:CustomAction.RunArg) -> bool:
        recover_manager.potion_stats.reset_usage()
        logging.info(f"[重置吃药数据] 重置已使用药水数量")
        return True



@AgentServer.custom_action("load_potion_limit")
class LoadPotionLimit(CustomAction):
    """读取药水设置"""
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        # 获取设置参数
        try:
             params = common_func.parse_params(
                param_str=argv.custom_action_param,
                node_name=argv.node_name,
                required_keys=["ap_big", "ap_small","bc_big","bc_small"]
            )
        except ValueError as e:
            # 参数检查不通过，打印失败原因
            logging.error(f"[{argv.node_name}] 参数解析失败: {e}")
            return CustomAction.RunResult(success=False)

        # 提取出每个参数
        ap_big = int(params["ap_big"])
        ap_small = int(params["ap_small"])
        bc_big = int(params["bc_big"])
        bc_small = int(params["bc_small"])

        # 设置药水限制数
        stats = recover_manager.potion_stats # 简写一下
        stats.ap.set_limit(ap_big,ap_small)
        stats.bc.set_limit(bc_big,bc_small)

        msg = (
            f"[{argv.node_name}] 药水设置载入 | "
            f"AP(大/小): {stats.ap.big.limit}/{stats.ap.small.limit} | "
            f"BC(大/小): {stats.bc.big.limit}/{stats.bc.small.limit} | "
        )
        logging.info(msg)
        return CustomAction.RunResult(success=True)
    
@AgentServer.custom_action("load_free_recover")
class LoadFreeRecover(CustomAction):
    """读取药水设置"""
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        # 获取设置参数
        try:
             params = common_func.parse_params(
                param_str=argv.custom_action_param,
                node_name=argv.node_name,
                required_keys=["free_recover"]
            )
        except ValueError as e:
            # 参数检查不通过，打印失败原因
            logging.error(f"[{argv.node_name}] 参数解析失败: {e}")
            return CustomAction.RunResult(success=False)

        # 使用 str().lower() 是为了兼容 UI 传过来的可能是 JSON 的 true (bool) 
        # 也可以是字符串的 "True"/"true"。
        # 只要它是 "true"，结果就是 True；如果是 "false"，结果自动就是 False。
        free_recover = str(params["free_recover"]).lower() == "true"

        # 设置免费恢复情况
        stats = recover_manager.potion_stats # 简写一下
        stats.use_free_recover = free_recover
        msg = (
            f"免费吃药: {'是' if stats.use_free_recover else '否'}"
        )
        logging.info(msg)
        return CustomAction.RunResult(success=True)
