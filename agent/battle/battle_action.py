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
            common_func.dynamic_set_next(context, pre_node="放生分流", next_node="放生-放弃感染")
            msg = f"[{argv.node_name}] 已将放生分流重定向为放生分支"
        else:
            common_func.dynamic_set_next(context, pre_node="放生分流", next_node="战斗失败处理")
            msg = f"[{argv.node_name}] 已将放生分流重定向为战斗失败"

        logging.info(msg)
        return CustomAction.RunResult(success=True)
    
@AgentServer.custom_action("battle_win")
class BattleWin(CustomAction):
    """战斗胜利时进行的相关处理,需要增加战斗次数、归档相关信息，并且输出反馈。"""
    def run(self,context:Context,argv:CustomAction.RunArg) -> bool:
        # 增加战斗次数
        battle_manager.active_context.battle_count += 1

        # 进行战斗归档
        battle_manager.archive_battle_result("胜利")

        # 设置输出信息
        current = battle_manager.active_context
        if current.battle_count == 1:
            # 一次性获得胜利
            msg = f"[🗡️ 一击胜利] {current.level}级 {current.category}感染者 {current.name}"
        else:
            # 多次战斗获得胜利
            msg = f"[⚔️ 多次交战] {current.level}级 {current.category}感染者 {current.name} | 击杀花费次数: {current.battle_count}"

        common_func.dynamic_set_focus(context,"输出战斗信息","RECO_OK",msg)
        return CustomAction.RunResult(success=True)
    
@AgentServer.custom_action("battle_lose")
class BattleLose(CustomAction):
    """战斗失败时进行的相关处理,只需要增加战斗次数"""
    def run(self,context:Context,argv:CustomAction.RunArg) -> bool:
        battle_manager.active_context.battle_count += 1
        return CustomAction.RunResult(success=True)
    
@AgentServer.custom_action("battle_release")
class BattleRelease(CustomAction):
    """放生结束后的处理。"""
    def run(self,context:Context,argv:CustomAction.RunArg) -> bool:
        # 虽然用不上，但还是增加战斗次数。
        current = battle_manager.active_context
        current.battle_count += 1

        # 归档放生信息
        battle_manager.archive_battle_result("放生")

        # 从档案中获取累计放生次数
        profile = battle_manager.archives.get(current.name)
        release_count = profile.get_record_by_mode(current.mode).release if profile else 1

        # 整理用户需要看到的信息
        focus_msg = f"[👋 放生] {current.level}级 {current.category}感染者 {current.name} | 累计放生: {release_count}"
        common_func.dynamic_set_focus(context,"输出战斗信息","RECO_OK",focus_msg)

        # 如果需要发送公屏信息,进行相关处理
        if battle_manager.current_config.broadcast:
            # 将后续节点导向公屏模块
            common_func.dynamic_set_next(context,"放生广播分流","开始公屏发送")

            # 整理公屏需要发送的信息
            broadcast_msg = f"[自动发送] {current.category} {current.name} LV.{current.level} {battle_manager.current_config.broadcast_addition}"
            context.override_pipeline({
                "公屏输入文字":{
                    "input_text":broadcast_msg
                }
            })

            # 执行完公屏模块之后，回到战斗模块(测试期间会关闭点击发送消息的 enabled,防止发送错误消息 )
            common_func.dynamic_set_next(context,"点击发送消息","放生结束")
        else:
            common_func.dynamic_set_next(context,"放生广播分流","放生结束")

        return CustomAction.RunResult(success=True)



