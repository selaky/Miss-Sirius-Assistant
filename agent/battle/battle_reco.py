from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context
from . import battle_manager
import logging
import re

@AgentServer.custom_recognition("extract_enemy_info")
class ExtractEnemyInfo(CustomRecognition):
    """利用 ocr 提取敌人信息并更新"""
    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        reco_detail = context.run_recognition("EnemyInfo",argv.image)
        if reco_detail and reco_detail.hit:
            ocr_text = reco_detail.best_result.text
        else:
            msg = f"[{argv.node_name}] 未识别到有效 OCR 结果"
            logging.info(msg)
            raise ValueError(msg)
        
        # 提取感染者姓名、状态和等级
        # ocr 识别结果示例:
        # CODE-23LV.89
        # 晶晶LV.215
        # 暴走的天狼星LV.5
        pattern = r"(.*?)LV\.(\d+)" # 提取信息用的正则表达式模具
        clean_text = ocr_text.replace(" ", "").replace("\n", "").replace("\r", "") # 去除空格或换行符
        match = re.search(pattern,clean_text,re.IGNORECASE)

        if not match:
            msg = f"[{argv.node_name}] OCR 数据格式错误，无法解析: '{ocr_text}'"
            raise ValueError(msg)
        
        # 提取原始数据
        raw_name = match.group(1)
        level_str = match.group(2)

        # 转换等级为整数(前面的步骤保证了这一步一定是数字)
        level = int(level_str)
        
        # 如果名字里有"暴走的"三个字，就是暴走感染者
        is_rampage = "暴走的" in raw_name
        # 把"暴走的"从名字里去掉
        final_name = raw_name.replace("暴走的", "")
        # 记录当前模式
        mode = "暴走" if is_rampage else "一般"

        # 登记感染者信息,更新战斗上下文。
        battle_manager.update_encounter_context(final_name,mode,level)

        msg = f"[{argv.node_name}] 识别到 {level}级 {mode} 感染者 {final_name}"
        return CustomRecognition.AnalyzeResult(box=(0, 0, 0, 0), detail=msg)