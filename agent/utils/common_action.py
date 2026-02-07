from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
import logging
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
        except ValueError as e:
            # 参数检查不通过，打印失败原因
            logging.error(f"[{argv.node_name}] 参数解析失败: {e}")
            return CustomAction.RunResult(success=False)
        
        # 单独提取出两个参数
        pre_node = str(params["pre_node"])
        next_node = str(params["next_node"])
        logging.info(f"[{argv.node_name}] 正在将 {pre_node} 的路由重定向至 {next_node}")

        # 将指定节点的 next 改写为要求的 next 列表
        common_func.dynamic_set_next(context,pre_node,next_node)
        return CustomAction.RunResult(success=True)
    
@AgentServer.custom_action("click_all_custom_reco")
class ClickAllCustomReco(CustomAction):
    """
    点击自定义识别返回的所有按钮
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        # 获取所有需要点击的位置
        click_targets = argv.reco_detail.best_result.detail.get("click_targets", [])
        if not click_targets:
            logging.info(f"[{argv.node_name}] 没有需要点击的按钮，跳过。")
            return CustomAction.RunResult(success=True)
        logging.info(f"[{argv.node_name}] 开始执行点击，共 {len(click_targets)} 个目标。")
        # 从字典列表中提取 ROI 列表
        roi_list = [target["roi"] for target in click_targets]
        common_func.group_click(context, roi_list)

        return CustomAction.RunResult(success=True)