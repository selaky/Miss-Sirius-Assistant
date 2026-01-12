# input:暂无
# output: 各类模块
# pos: 为各个模块提供通用工具。

from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context
import logging
from datetime import datetime
import json

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
        try:
            if not argv.custom_recognition_param:
                raise ValueError("参数为空！请在节点配置中填写 custom_params")
            params = json.loads(argv.custom_recognition_param)
        except json.JSONDecodeError:
            # 这是一个无法挽回的配置错误，必须大声报错
            error_msg = f"参数格式错误，必须是标准 JSON 格式。当前收到: {argv.custom_recognition_param}"
            logging.error(f"[{argv.node_name}] {error_msg}")
            # 主动抛出异常，中断执行，或者返回错误信息让框架处理
            raise ValueError(error_msg)
        
        try:
            # 强转 int 也是必须的，如果用户传了 "abc"，这里会抛出 ValueError
            target_hour = int(params["target_hour"]) 
            target_minute = int(params["target_minute"])
        except KeyError as e:
            error_msg = f"缺少必要参数: {e}。请检查是否填写了 target_hour 和 target_minute"
            logging.error(f"[{argv.node_name}] {error_msg}")
            raise ValueError(error_msg)
        except ValueError as e:
            error_msg = f"时间参数必须是整数数字！当前参数: {params}"
            logging.error(f"[{argv.node_name}] {error_msg}")
            raise ValueError(error_msg)

        # 调用判断
        try:
            should_stop = is_after_target_time(target_hour, target_minute)
        except ValueError as e:
            error_msg = f"时间数值不合法 (例如小时>23或分钟>59): {target_hour}:{target_minute}"
            logging.error(f"[{argv.node_name}] {error_msg}")
            raise ValueError(error_msg)

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