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
    
@AgentServer.custom_action("click_4_star_filter")
class Click4StarFilter(CustomAction):
    """
    筛选出所有的四星卡。
    实际上此操作筛选出来的是四星及以下的所有卡，
    但是因为本行为会在一、二、三星卡全都进行实验之后执行，因此实际留下的只有四星
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        # 获取所有需要点击的位置
        click_targets = argv.reco_detail.detail.get("click_targets", [])
        if not click_targets:
            logging.info(f"[{argv.node_name}] 没有需要点击的筛选按钮，跳过。")
            return CustomAction.RunResult(success=True)
        logging.info(f"[{argv.node_name}] 开始执行点击，共 {len(click_targets)} 个目标。")
        common_func.group_click(context,click_targets)

        return CustomAction.RunResult(success=True)
    
@AgentServer.custom_action("click_all_card")
class Click4StarFilter(CustomAction):
    """
    逐个点击当前页面上的全部六张卡牌
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        common_func.group_click(context,lab_manager.card_slots)

        return CustomAction.RunResult(success=True)