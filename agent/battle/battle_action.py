# input: battle_manager
# output: 暂无
# pos: 战斗相关动作

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from . import battle_manager
import logging
import json
from utils import common_func

@AgentServer.custom_action("set_enemy_next")
class SetEnemyNext(CustomAction):
    """根据当前敌人信息进行后续分流设置"""
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
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
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        # 增加战斗次数
        battle_manager.active_context.battle_count += 1

        # 进行战斗归档
        battle_manager.archive_battle_result("胜利")

        # 设置输出信息
        current = battle_manager.active_context
        if current.battle_count == 1:
            # 一次性获得胜利
            msg = f"[🗡️击败] {current.name} LV.{current.level} {current.mode} "
        else:
            # 多次战斗获得胜利
            msg = f"[⚔️击败] {current.name} LV.{current.level} {current.mode} | 击杀花费次数: {current.battle_count}"

        common_func.dynamic_set_focus(context,"输出战斗信息","RECO_OK",msg)
        return CustomAction.RunResult(success=True)
    
@AgentServer.custom_action("battle_lose")
class BattleLose(CustomAction):
    """战斗失败时进行的相关处理,只需要增加战斗次数"""
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        battle_manager.active_context.battle_count += 1
        return CustomAction.RunResult(success=True)
    
@AgentServer.custom_action("battle_release")
class BattleRelease(CustomAction):
    """放生结束后的处理。"""
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        # 虽然用不上，但还是增加战斗次数。
        current = battle_manager.active_context
        current.battle_count += 1

        # 归档放生信息
        battle_manager.archive_battle_result("放生")

        # 从档案中获取累计放生次数
        profile = battle_manager.archives.get(current.name)
        release_count = profile.get_record_by_mode(current.mode).release if profile else 1

        # 整理用户需要看到的信息
        focus_msg = f"[👋 放生] {current.name} LV.{current.level} {current.mode} | 累计放生: {release_count}"
        common_func.dynamic_set_focus(context,"输出战斗信息","RECO_OK",focus_msg)

        # 如果需要发送公屏信息,进行相关处理
        if battle_manager.current_config.broadcast:
            # 将后续节点导向公屏模块
            common_func.dynamic_set_next(context,"放生广播分流","开始公屏发送")

            # 整理公屏需要发送的信息
            broadcast_msg = f"[感染者] {current.name} {current.mode} {battle_manager.current_config.broadcast_addition}"
            context.override_pipeline({
                "公屏输入文字":{
                    "input_text":broadcast_msg
                }
            })

            # 执行完公屏模块之后，回到战斗模块(测试期间会关闭点击发送消息的点击行为,防止发送错误消息 )
            common_func.dynamic_set_next(context,"点击发送消息","放生结束")
        else:
            common_func.dynamic_set_next(context,"放生广播分流","放生结束")

        return CustomAction.RunResult(success=True)


@AgentServer.custom_action("save_battle_config")
class SaveBattleConfig(CustomAction):
    """
    通用战斗配置保存动作。
    通过 custom_action_param 传入 config_key 和 config_value，
    自动将配置项保存到 battle_manager.current_config 中。
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        # 解析参数
        params = common_func.parse_params(
            param_str=argv.custom_action_param,
            node_name=argv.node_name,
            required_keys=["config_key", "config_value"]
        )

        config_key = params["config_key"]
        config_value = params["config_value"]

        # 调用 manager 的设置函数
        try:
            battle_manager.set_config_value(config_key, config_value)
            logging.info(f"[{argv.node_name}] 已保存配置: {config_key} = {config_value}")
        except ValueError as e:
            logging.error(f"[{argv.node_name}] 配置保存失败: {e}")
            return CustomAction.RunResult(success=False)

        return CustomAction.RunResult(success=True)


@AgentServer.custom_action("finalize_battle_config")
class FinalizeBattleConfig(CustomAction):
    """
    完成战斗配置设置。
    标记配置已完成，并输出配置摘要。
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        # 标记配置完成
        battle_manager.set_config_value("mark_configured", True)

        # 输出配置摘要
        summary = battle_manager.get_config_summary()
        logging.info(f"[{argv.node_name}] 战斗配置完成:\n{summary}")

        # 设置 focus 消息显示给用户
        common_func.dynamic_set_focus(
            context,
            "战斗设置完成",
            "RECO_OK",
            "战斗设置已保存，可以开始跑图任务"
        )

        return CustomAction.RunResult(success=True)


@AgentServer.custom_action("check_battle_config")
class CheckBattleConfig(CustomAction):
    """
    检查战斗配置是否已完成。
    如果未配置，通过 focus 提示用户先执行设置任务，并返回失败。
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        if not battle_manager.check_configured():
            error_msg = "请先执行【跑图战斗设置】任务进行战斗配置！"
            logging.error(f"[{argv.node_name}] {error_msg}")

            # 设置 focus 消息提示用户
            common_func.dynamic_set_focus(
                context,
                "检查战斗配置",
                "RECO_OK",
                error_msg
            )

            return CustomAction.RunResult(success=False)

        logging.info(f"[{argv.node_name}] 战斗配置检查通过")
        return CustomAction.RunResult(success=True)


@AgentServer.custom_action("reset_battle_data")
class ResetBattleData(CustomAction):
    """重置战斗信息"""
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        battle_manager.reset_enemy_data()
        logging.info(f"[{argv.node_name}] 重置战斗统计信息（敌人档案、战绩记录）")
        return CustomAction.RunResult(success=True)
