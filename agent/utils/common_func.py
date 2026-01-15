# input:暂无
# output: 各类模块
# pos: 为各个模块提供通用工具。

from datetime import datetime
from typing import Dict, List, Any
import json
import logging
from maa.context import Context

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

def parse_params(param_str:str,node_name:str,required_keys:List[str]=None)->Dict[str,Any]:
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
    
    # 处理默认的可变参数
    if required_keys is None:
        required_keys = []
    
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

def dynamic_set_next(context: Context, pre_node: str, next_node: str):
    """
    通用函数：修改指定节点的 next 指向
    :param context: MAA 的上下文对象，是操作的核心句柄
    :param pre_node: 要修改的节点名
    :param next_node: 目标节点名
    """
    # 这里不做过多的参数校验（如是否为空），保持函数的纯粹性。   
    context.override_pipeline({
        pre_node: {
            "next": [next_node]
        }
    })
    return True


# 定义 focus 消息类型标准常量
class FocusType:
    RECO_START = "Node.Recognition.Starting"     # 识别开始
    RECO_OK  = "Node.Recognition.Succeeded"    # 识别成功
    RECO_FAIL  = "Node.Recognition.Failed"       # 识别失败
    ACT_START = "Node.Action.Starting"          # 动作开始
    ACT_OK  = "Node.Action.Succeeded"         # 动作成功
    ACT_FAIL  = "Node.Action.Failed"            # 动作失败

def dynamic_set_focus(context: Context, target_node: str, trigger: str, focus_msg: str):
    """
    通用函数：修改指定节点的 focus
    """
    
    # 处理触发时机的转换
    search_key = trigger.upper() # 把输入转成全大写,容错率更高。
    # 尝试从 FocusType 类中找 search_key 对应的变量,如果找不到就返回None
    real_trigger_str = getattr(FocusType,search_key,None)
    # 校验输入是否有效
    if real_trigger_str is None:
        # 打印出所有合法的变量名供调试参考
        valid_keys = [k for k in dir(FocusType) if not k.startswith("__")]
        logging.error(f"[SetFocus] 参数错误: 找不到名为 '{search_key}' 的触发时机。可用值: {valid_keys}")
        return False
        
    final_trigger = real_trigger_str # 只是为了让名字短点
    logging.info(f"[SetFocus] 配置: {target_node} -> [{final_trigger}] -> Focus={focus_msg}")

    # 将指定节点的 focus 改写
    context.override_pipeline({
        target_node:{
            "focus":{final_trigger:focus_msg}
        }
    })
    return True

def extract_number_from_ocr(context: Context, image, task_name: str) -> int:
    """
    通用工具：执行指定 OCR 任务并提取其中的纯数字。
    
    Args:
        context: MFW 的上下文对象
        image: 当前画面的图片数据
        task_name: pipeline.json 中定义的 OCR 任务名称
        
    Returns:
        int: 提取到的数字
        None: 如果没识别到、没文字、或文字里没有数字，则返回 None
    """
    # 执行 ocr 节点
    reco_detail = context.run_recognition(task_name,image)

    # 校验没有结果或未命中的情况
    if not reco_detail or not reco_detail.hit:
        raise ValueError(f"OCR任务 [{task_name}] 未命中或识别失败")
    
    # 获取最佳结果
    best = getattr(reco_detail,"best_result",None)
    if not best:
        raise ValueError(f"OCR任务 [{task_name}] 命中但无 best_result")
    
    # 提取文本并清洗出数字
    text = getattr(best,"text","")
    digits = "".join(ch for ch in (text or "") if ch.isdigit())

    if not digits:
        raise ValueError(f"OCR任务 [{task_name}] 识别到了文本 '{text}' 但其中不包含数字")
    
    return int(digits)
