# input: boss_manager 提供数据和判断方法
# output: 为是否执行 boss_action 提供决策
# pos: boss 战相关行为的决策部分

from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context
from . import boss_manager
import logging


@AgentServer.custom_recognition("should_boss_stop")
class ShouldBossStop(CustomRecognition):
    """判断 boss 战是否停止"""
    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        # 别名设置
        stats = boss_manager.boss_stats

        # 记录当前战斗次数进度，如果最大战斗次数为负一，显示为无穷。
        if stats.max_battles == -1:
            progress = f"{stats.current_battles}/∞"
        else:
            progress = f"{stats.current_battles}/{stats.max_battles}"

        # 判断是否继续
        if stats.should_stop:
            msg = f"战斗次数达到上限 {progress}，boss 战停止。"
            logging.info(f"[{argv.node_name}] {msg}")
            return CustomRecognition.AnalyzeResult(box=(0, 0, 0, 0), detail=msg)
        else:
            msg = f"当前战斗次数 {progress},继续战斗。"
            logging.info(f"[{argv.node_name}] {msg}")
            return CustomRecognition.AnalyzeResult(box=None, detail=msg)
        
@AgentServer.custom_recognition("should_boss_pause")
class ShouldBossPause(CustomRecognition):
    """判断是否已达到目标排名，需要等待一会"""
    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        # 别名设置
        stats = boss_manager.boss_stats

        # 确认当前在 boss 界面
        reco_detail = context.run_recognition("BossPage",argv.image)
        if not reco_detail or not reco_detail.hit:
            msg = "未识别到 boss 界面."
            return CustomRecognition.AnalyzeResult(box=None, detail=msg)
        
        # 获取当前排名
        current_rank = 999
        reco_rank = context.run_recognition("CurrentRank",argv.image)

        # 数字 OCR 处理抄 M9A 的代码
        if reco_rank:
            if not reco_rank.hit: # 没识别到排名数字,可能还没打过，先去打一场。
                msg = "未识别到排名,可能尚未进行初次战斗或识别失败,将会继续战斗流程。"
                return CustomRecognition.AnalyzeResult(box=None, detail=msg)
            else:
                best = getattr(reco_rank,"best_result",None)
                if best:
                    text = getattr(best,"text","")
                    digits = "".join(ch for ch in (text or "") if ch.isdigit())
                    if digits:
                        current_rank = int(digits)
                    else:
                        return CustomRecognition.AnalyzeResult(box=None, detail="OCR警告：识别到区域但无法提取有效数字")
                else:
                    msg = "OCR警告：未提取到 best_result,保险起见先进行战斗。"
                    return CustomRecognition.AnalyzeResult(box=None, detail=msg)

        # 更新储存的当前排名
        stats.current_rank = current_rank

        # 记录排名与目标数
        if stats.target_rank == -1:
            rank_report = f"当前排名: {stats.current_rank}| 目标: 冲榜(无上限)"
        else:
            rank_report = f"当前排名: {stats.current_rank}| 目标: <= {stats.target_rank}."

        # 调用方法判断是否需要暂停
        if stats.should_pause:
            msg = f"{rank_report}\n-> 已达标，暂停等待。"
            return CustomRecognition.AnalyzeResult(box=(0, 0, 0, 0), detail=msg)
        else:
            msg = f"{rank_report}\n-> 未达标，继续战斗。"
            return CustomRecognition.AnalyzeResult(box=None, detail=msg)

