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
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        boss_manager.boss_stats.current_battles += 1
        logging.info(f"[{argv.node_name}] BOSS战斗计数 +1，当前: {boss_manager.boss_stats.current_battles}")
        return CustomAction.RunResult(success=True)


@AgentServer.custom_action("load_boss_data")
class LoadBossData(CustomAction):
    """加载BOSS战配置参数"""
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        # 从 custom_action_param 读取配置
        params = argv.custom_action_param
        if isinstance(params, str):
            params = json.loads(params) if params else {}

        max_battles = params.get("max_battles", -1)
        target_rank = params.get("target_rank", -1)

        # 设置参数
        boss_manager.boss_stats.max_battles = max_battles
        boss_manager.boss_stats.target_rank = target_rank

        logging.info(f"[{argv.node_name}] 加载BOSS配置: max_battles={max_battles}, target_rank={target_rank}")
        return CustomAction.RunResult(success=True)
