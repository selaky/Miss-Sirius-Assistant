# input: recover_helper
# output: 暂无
# pos: 这里是恢复流程中执行的动作

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from . import recover_helper
import logging
import json

@AgentServer.custom_action("init_potion_data")
class InitPotionData(CustomAction):
    """初始化药水数据"""
    def run(self,context:Context,argv:CustomAction.RunArg) -> bool:
        logging.info(f"[初始化吃药数据] 正在重置已使用药水数量")
        recover_helper.potion_stats.reset_usage()

        try:
            # 读取参数
            params = json.loads(argv.custom_action_param)
            ap_big = int(params.get("ap_big",0))
            ap_small = int(params.get("ap_small",0))
            bc_big = int(params.get("bc_big",0))
            bc_small = int(params.get("bc_small",0))
            # 设置药水限制数
            stats = recover_helper.potion_stats # 简写一下
            stats.ap.set_limit(ap_big,ap_small)
            stats.bc.set_limit(bc_big,bc_small)
            logging.info(
                f"[初始化吃药数据] 药品使用上限载入\n"
                f"大行动力恢复药: {stats.ap.big.limit}\n"
                f"小行动力恢复药: {stats.ap.small.limit}\n"
                f"大战斗力恢复药: {stats.bc.big.limit}\n"
                f"小战斗力恢复药: {stats.bc.small.limit}"
            )

            # logging.info(f"debug: ap_big 的类型是 {type(ap_big)}")
            
            return True
        except Exception as e:
            logging.error(f"[初始化吃药数据]参数解析失败或设置出错:{e}")
            return False

@AgentServer.custom_action("store_potion_storage")
class StorePotionStorage(CustomAction):
    """储存 OCR 识别到的药水数量"""
    def run(self,context:Context,argv:CustomAction.RunArg) -> bool:
        try:
            node_name = argv.node_name
            # 获取 OCR 结果
            ocr_res = int(argv.reco_detail.best_result.text)
            logging.info(f"{node_name} OCR 识别结果为 {ocr_res}")

            # 进行节点解析
            
            potion_type = recover_helper.node_name_extract(node_name)

            # 将 OCR 结果存入对应药水的记录中
            potion_type.stock = ocr_res
            logging.info(f"{node_name} 成功保存数据, {potion_type.name} 的剩余数量为 {potion_type.stock}")

            return True
        except Exception as e:
            logging.warning(f"[{node_name}]统计数据出错：{e}")
            return False
        
@AgentServer.custom_action("add_potion_usage")
class AddPotionUsage(CustomAction):
    """把药品使用计数+1"""
    def run(self,context:Context,argv:CustomAction.RunArg) -> bool:
        try:
            node_name = argv.node_name
            potion_type = recover_helper.node_name_extract(node_name)
            potion_type.inc_usage()
            logging.info(f"{potion_type.name}的使用量增加,现在为{potion_type.usage}")
            return True
        except Exception as e:
            logging.error(f"{potion_type.name}+1失败")
            return False