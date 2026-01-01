# input: arena_helper 提供竞技场数据管理
# output: 暂无
# pos: 竞技场相关的识别,判断当前积分是否小于目标积分。

from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context
from . import arena_helper
import logging

stats = arena_helper.arena_stats # 简写

@AgentServer.custom_recognition("should_continue_arena")
class ShouldContinueArena(CustomRecognition):
    def analyze(self, context: Context, argv: CustomRecognition.AnalyzeArg) -> CustomRecognition.AnalyzeResult:
        """判断当前积分是否已达到目标积分，如果达到就停止竞技场。"""
        try:
            current_points = stats.current_points
            target_points = stats.target_points
            if current_points < target_points:
                msg = f"[判断继续竞技场]当前积分{current_points}, 小于目标积分{target_points},继续战斗"
                logging.info(msg)
                return CustomRecognition.AnalyzeResult(box=(0, 0, 100, 100), detail=msg)
            else:
                msg = f"[判断继续竞技场]当前积分{current_points}, 满足目标积分{target_points},停止战斗"
                logging.info(msg)
                return CustomRecognition.AnalyzeResult(box=None, detail=msg)
        except Exception as e:
            msg = f"[判断继续竞技场]出错: {e}"
            logging.error(msg)
            return CustomRecognition.AnalyzeResult(box=None, detail=msg)
