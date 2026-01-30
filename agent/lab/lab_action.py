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
    def run(self,context:Context,argv:CustomAction.RunArg) -> bool:
        common_func.group_click(context,lab_manager.batch_select_rois)
        return CustomAction.RunResult(success=True)