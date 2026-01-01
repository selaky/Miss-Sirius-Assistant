# input: arena_helper 提供竞技场数据管理
# output: 暂无
# pos: 竞技场相关的动作,包括初始化数据记录当前积分，增加胜利或失败次数，输出数据统计。

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from . import arena_helper
import logging
import json

stats = arena_helper.arena_stats # 简写

@AgentServer.custom_action("init_arena_data")
class InitArenaData(CustomAction):
    """初始化竞技场数据"""
    def run(self,context:Context,argv:CustomAction.RunArg) -> bool:
        logging.info(f"[初始化竞技场数据] 正在重置战斗数据")
        arena_helper.arena_stats.reset_arena()

        try:
            # 读取参数
            params = json.loads(argv.custom_action_param)
            target_points = int(params.get("target_points",0))
            # 记录目标积分
            stats.target_points = target_points
            logging.info(f"[初始化竞技场数据] 将目标分数记录为 {stats.target_points}")

            return True
        except Exception as e:
            logging.error(f"[初始化竞技场数据]初始化失败: {e}")
            return False
        
@AgentServer.custom_action("store_current_arena_points")
class StoreCurrentArenaPoints(CustomAction):
    """储存 OCR 识别到的当前积分"""
    def run(self,context:Context,argv:CustomAction.RunArg) -> bool:
        try:
            # 获取 OCR 结果
            ocr_res = int(argv.reco_detail.best_result.text)
            logging.info(f"[记录竞技场积分] OCR 识别结果为 {ocr_res}")

            # 储存 OCR 结果
            stats.current_points = ocr_res
            logging.info(f"[记录竞技场积分]已保存当前竞技场积分为 {stats.current_points}")

            return True
        except Exception as e:
            logging.error(f"[记录竞技场积分] 出错: {e}")
            return False

@AgentServer.custom_action("store_arena_result")
class StoreArenaResult(CustomAction):
    """根据当前战斗结果是胜利还是失败，将相关统计数据加一"""
    def run(self,context:Context,argv:CustomAction.RunArg) -> bool:
        try:
            node_name = argv.node_name # 取当前节点名。

            if "胜利" in node_name:
                stats.win_count += 1
                logging.info(f"竞技场获胜，当前胜利场数{stats.win_count}")
            elif "失败" in node_name:
                stats.loss_count += 1
                logging.info(f"竞技场失败，当前失败场数{stats.loss_count}")
            else:
                raise ValueError((f"致命错误：在名称 '{node_name}' 中未识别战斗结果(胜利/失败)！请确保你在正确的节点调用此动作，并且对节点规范命名。"))
            return True
        except Exception as e:
            logging.error(f"竞技场战斗结果记录失败: {e}")
            return False
            
@AgentServer.custom_action("set_arena_results")
class SetArenaResults(CustomAction):
    """在 GUI 界面展示竞技场相关结果"""
    def run(self,context:Context,argv:CustomAction.RunArg) -> bool:
        try:
            # 简写一下
            win = stats.win_count
            loss = stats.loss_count

            # 计算胜率
            if win+loss != 0:
                win_rate = win/(win+loss)
            else:
                win_rate = 0

            # 直接拼接完整的消息字符串
            message = (
                f"竞技场战斗任务结束，目标 {stats.target_points} 积分，"
                f"当前 {stats.current_points} 积分。\n"
                f"胜利 {win} 场，失败 {loss} 场，胜率 {win_rate:.2%}"
            )

            # 使用 override_pipeline 修改当前节点的 focus 为完整字符串
            context.override_pipeline({
                "输出竞技场数据统计":{
                    "focus":{
                        "Node.Action.Succeeded": message
                    }
                }
            })

            return True
        except Exception as e:
            logging.error(f"[输出竞技场数据统计]出错:{e}")
            return False

