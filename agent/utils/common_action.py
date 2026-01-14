from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
import logging
import json
from . import common_func

@AgentServer.custom_action("set_next")
class SetNext(CustomAction):
    """将指定节点的 next 指向目标节点"""
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        
        # 获取设置参数
        try:
             params = common_func.parse_params(
                param_str=argv.custom_action_param,
                node_name=argv.node_name,
                required_keys=["pre_node", "next_node"]
            )
        except ValueError:
            # 参数检查不通过
            return CustomAction.RunResult(success=False)
        
        # 单独提取出两个参数
        pre_node = str(params["pre_node"])
        next_node = str(params["next_node"])
        logging.info(f"[{argv.node_name}] 正在将 {pre_node} 的路由重定向至 {next_node}")

        # 将指定节点的 next 改写为要求的 next 列表
        context.override_pipeline({
            pre_node:{
                "next":[next_node]
            }
        })
        return CustomAction.RunResult(success=True)