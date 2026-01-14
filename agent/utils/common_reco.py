from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context
import logging
import json
from . import common_func

@AgentServer.custom_recognition("check_deadline")
class CheckDeadline(CustomRecognition):
    """通用时间截止检查器"""
    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
          
        # 获取用户参数
        params = common_func.parse_params(
                param_str=argv.custom_recognition_param, 
                node_name=argv.node_name, 
                required_keys=["target_hour", "target_minute"]
            )
        
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
            should_stop = common_func.is_after_target_time(target_hour, target_minute)
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