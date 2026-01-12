from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from . import boss_manager
import logging
import json

@AgentServer.custom_action("reset_boss_data")
class ResetPotionData(CustomAction):
    """重置BOSS数据"""
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        boss_manager.boss_stats.current_battles = 0
        logging.info(f"[{argv.node_name}] 重置BOSS已战斗次数")
        return CustomAction.RunResult(success=True)
    
@AgentServer.custom_action("add_boss_battles")
class AddBossBattles(CustomAction):
    """增加已经进行 boss 战的数量"""
    boss_manager.boss_stats.current_battles += 1
    
        