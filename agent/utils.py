# input:暂无
# output: 各类模块
# pos: 为各个模块提供通用工具。

from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context
import logging
from datetime import datetime

def is_after_target_time(target_hour:int,target_minute:int) -> bool:
        """
    判断当前时间是否已经晚于今天的指定时间。
    
    参数:
        target_hour (int): 目标小时 (0-23)
        target_minute (int): 目标分钟 (0-59)
        
    返回:
        bool: 如果当前时间 >= 目标时间，返回 True；否则返回 False
    """
        # 获取当前系统时间
        now = datetime.now()

        # 构建目标时间对象
        target_time = now.replace(
                hour = target_hour,
                minute = target_minute,
                second = 0,
                microsecond = 0
                )
        
        #直接利用 Python 的对象比较功能
        # Python 的 datetime 对象支持 >, <, >=, <= 操作符
        # 如果 now 在时间轴上位于 target_time 之后，结果就是 True
        return now >= target_time

@AgentServer.custom_recognition("check_deadline")
class CheckDeadline(CustomRecognition):
    """通用时间截止检查器"""
    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
          
          # 获取用户参数
          params = argv.custom_recognition_param
          target_hour = int(params.get("target_hour",23))
          target_minute = int(params.get("target_minute",59))

          # 调用判断
          should_stop = is_after_target_time(target_hour,target_minute)

          # 构造便于阅读的时间字符串
          time_str = f"{target_hour:02d}:{target_minute:02d}"

          # 返回结果
          if should_stop:
                msg = f"当前已超过设定截止时间 {time_str}，触发停止逻辑。"
                logging.info(f"[{argv.node_name}] {msg}")
                return CustomRecognition.AnalyzeResult(box=(0, 0, 0, 0), detail=msg)
          else:
                msg = f"当前未到截止时间 {time_str}，任务继续。"
                return CustomRecognition.AnalyzeResult(box=None, detail=msg)