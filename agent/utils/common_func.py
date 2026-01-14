# input:暂无
# output: 各类模块
# pos: 为各个模块提供通用工具。

from datetime import datetime
from typing import Dict, List, Any
import json
import logging

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

def parse_params(param_str:str,node_name:str,required_keys:List[str]=[])->Dict[str,any]:
    """
    解析节点参数，确定所需参数都在,并将正确格式返回。
    
    Args:
        param_str: 参数的原始 JSON 字符串 (str)
        node_name: 节点名称，用于日志报错 (str)
        required_keys: 必填字段检查 (List[str])

    举例:
    手动把 argv.custom_recognition_param 拿出来传进去
    params = parse_params(
        param_str=argv.custom_recognition_param, 
        node_name=argv.node_name, 
        required_keys=["target_hour", "target_minute"]
    )
    """
    # 判断是否为空
    if not param_str:
        error_msg = "参数为空！请在节点配置中填写 custom_params"
        raise ValueError(error_msg)
    
    # 解析 JSON
    try:
        params = json.loads(param_str)
    except json.JSONDecodeError:
        error_msg = f"参数格式错误，不是标准 JSON。收到: {param_str}"
        logging.error(f"[{node_name}] {error_msg}")
        raise ValueError(error_msg)

    # 检查必填项
    missing_keys = [k for k in required_keys if k not in params]
    if missing_keys:
        error_msg = f"缺少必要参数: {missing_keys}。当前参数: {params}"
        logging.error(f"[{node_name}] {error_msg}")
        raise ValueError(error_msg)
    return params
        
