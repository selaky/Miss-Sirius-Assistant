# input: states
# output: 暂无
# pos: 这里是恢复流程中执行的动作

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
import recover_helper
import logging
import json

# 把日志级别调成 info, 看一下数据有没有正常读取。
logging.basicConfig(level=logging.INFO) 

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

        