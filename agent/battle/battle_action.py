# input: battle_manager
# output: 暂无
# pos: 战斗相关动作

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from . import battle_manager
import logging
from utils import common_func

@AgentServer.custom_action("set_enemy_next")
class SetEnemyNext(CustomAction):
    """根据当前敌人信息进行后续分流设置"""
    def run(self,context:Context,argv:CustomAction.RunArg) -> bool:
        # 获取当前决策
        info = battle_manager.active_context
        action = battle_manager.get_battle_action(info.name,info.mode)

        # 根据是否放生重定向后续节点
        if action.is_release_op:
            common_func.dynamic_set_next(pre_node="战斗分流",next_node="放生-进入战斗")
            msg = f"[{argv.node_name}] 已将战斗分流重定向为放生分支"
        else:
            common_func.dynamic_set_next(pre_node="战斗分流",next_node="战斗-进入战斗")
            msg = f"[{argv.node_name}] 已将战斗分流重定向为战斗分支"

        logging.info(msg)
        return CustomAction.RunResult(success=True)

