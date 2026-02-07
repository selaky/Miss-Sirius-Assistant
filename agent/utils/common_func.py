# input:暂无
# output: 各类模块
# pos: 为各个模块提供通用工具。

from datetime import datetime
from typing import Dict, List, Any
import json
import logging
from maa.context import Context
import random

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
    
    # 提取区域内所有识别到的结果,并按照横坐标排序拼在一起变成完整提取文本
    all_blocks = reco_detail.filtered_results
    try:
        # 排序
        all_blocks.sort(key=lambda block: block.box[0])
    except Exception as e:
        # 如果连坐标都读不出来，说明数据结构异常，报错
        logging.error(f"排序 OCR 结果块时发生严重错误: {e}")
        return None
        # 组合文本,即使只识别到一个文本也没有问题
    ocr_text = "".join([b.text for b in all_blocks])
    
    # 清洗出数字
    digits = "".join(ch for ch in (ocr_text or "") if ch.isdigit())

    if not digits:
        raise ValueError(f"OCR任务 [{task_name}] 识别到了文本 '{ocr_text}' 但其中不包含数字")
    
    return int(digits)


def group_click(context: Context, roi_collection):
    # 如果传入的是字典，先转成列表
        targets_to_click = []
        if isinstance(roi_collection, dict):
            targets_to_click = list(roi_collection.values())
        elif isinstance(roi_collection,list):
            targets_to_click = roi_collection
        else:
            raise ValueError(f"ROI 清单格式不对，必须为字典或列表,当前收到的内容为: {roi_collection}")
        
        for index, item in enumerate(targets_to_click):
            target_x, target_y = 0, 0
            
            # item 可能是列表或元组，这里检查长度
            # 假设 ROI 是 [x, y, w, h]，坐标是 [x, y]
            if len(item) == 4:
                x, y, w, h = item
                # 在 ROI 范围内进行均匀随机
                # 虽然游戏本身不检测点击,这里的随机没啥必要,但反正也不麻烦,顺手做一下
                # 这里使用了 int() 确保坐标是整数
                target_x = random.randint(int(x), int(x + w))
                target_y = random.randint(int(y), int(y + h))
                
            elif len(item) == 2:
                x, y = item
                # 如果是坐标，直接使用
                target_x, target_y = int(x), int(y)
                
            else:
                # 快速失败：遇到格式不对的数据直接停下来，方便定位是哪个数据写错了
                raise ValueError(f"数据格式错误: 第 {index+1} 个数据长度异常 (期望 2 或 4，实际 {len(item)})。内容: {item}")
            # 执行点击
            # 传入计算好的 target_x, target_y
            context.tasker.controller.post_click(target_x, target_y).wait()

        return True