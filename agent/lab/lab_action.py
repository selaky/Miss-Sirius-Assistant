from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from . import lab_manager
import logging
import json
from utils import common_func

@AgentServer.custom_action("select_all_low_star")
class SelectAllLowStar(CustomAction):
    """依次点击所有一二三星卡"""
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        common_func.group_click(context, lab_manager.batch_select_rois)
        return CustomAction.RunResult(success=True)
    
    
@AgentServer.custom_action("click_all_card")
class ClickAllCard(CustomAction):
    """
    逐个点击当前页面上的全部六张卡牌
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        common_func.group_click(context,lab_manager.card_slots)

        return CustomAction.RunResult(success=True)
    
@AgentServer.custom_action("update_lab_mode")
class UpdateLabMode(CustomAction):
    """
    把当前节点的名字存起来
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        lab_manager.current_mode = argv.node_name
        return CustomAction.RunResult(success=True)
    
@AgentServer.custom_action("disable_lab_mode")
class DisableLabMode(CustomAction):
    """
    关闭当前正在执行的实验室任务模式
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        context.override_pipeline({
            lab_manager.current_mode: {
                "enabled": False
            }
        })

        return CustomAction.RunResult(success=True)