# input: recover_manager
# output: 暂无
# pos: 这里是恢复流程中识别的方式

from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context
from . import recover_manager
import logging
from utils import common_func

logging.basicConfig(level=logging.INFO) 

@AgentServer.custom_recognition("should_use_potion")
class ShouldUsePotion(CustomRecognition):

    # 需要点击的区域
    # ROI 可以写死,缩放问题框架会解决
    click_rois = {
        "big":[904,398,48,21], 
        "small":[902,514,49,21], 
        "free":[660,582,60,21], 
        "close":[994,259,20,21]
    }

    # 当免费恢复按钮的识别分数达到0.9以上时，说明按钮可点击。
    free_available_threshold = 0.9

    def analyze(self, context: Context, argv: CustomRecognition.AnalyzeArg) -> CustomRecognition.AnalyzeResult:
        """判断如何使用药水,并返回对应药水按钮的使用位置，或者是关闭按钮的位置,以供点击"""

        # 获取设置参数
        try:
             params = common_func.parse_params(
                param_str=argv.custom_recognition_param,
                node_name=argv.node_name,
                required_keys=["potion_type"]
            )
        except ValueError as e:
            # 参数检查不通过，打印失败原因
            msg = f"[{argv.node_name}] 参数解析失败: {e}"
            logging.error(msg)
            return CustomRecognition.AnalyzeResult(box=None, detail=msg)
        
        # 获取当前处理的药水种类
        potion_type = str(params["potion_type"]).upper()
        if potion_type == "AP":
            stats = recover_manager.potion_stats.ap
        elif potion_type == "BC":
            stats = recover_manager.potion_stats.bc
        else:
            raise ValueError(f"[{argv.node_name}] 药水种类参数填写错误,未识别到 ap 或者 bc.")
        
        # 利用免费恢复按钮，既确认是否在吃药界面，又能确认是否需要免费吃药
        reco_free = context.run_recognition("FreeRecover",argv.image)
        if not reco_free or not reco_free.hit:
            msg = f"[{argv.node_name}] 不在恢复界面"
            return CustomRecognition.AnalyzeResult(box=None, detail=msg)
        
        # 判断是否使用免费恢复
        best_free = getattr(reco_free,"best_result",None)
        if best_free and recover_manager.potion_stats.use_free_recover:
            score = float(getattr(best_free,"score",""))
            if score > self.free_available_threshold:
                click_roi = self.click_rois["free"]
                msg = f"使用免费恢复"
                next_node = "顺利完成吃药"
                common_func.dynamic_set_focus(context,target_node="输出恢复反馈",trigger="RECO_OK",focus_msg=msg)
                common_func.dynamic_set_next(context,pre_node="输出恢复反馈",next_node=next_node)
                logging.info(msg)
                return CustomRecognition.AnalyzeResult(box=click_roi, detail=msg)
            
        # OCR 获取当前药水库存
        try:
            big_stock = common_func.extract_number_from_ocr(context,argv.image,task_name="BigPotion")
            small_stock = common_func.extract_number_from_ocr(context,argv.image,task_name="SmallPotion")
        except ValueError as e:
            msg = f"[{argv.node_name}] {e}"
            return CustomRecognition.AnalyzeResult(box=None, detail=msg)
        
        # 储存 ocr 数字
        stats.big.stock = big_stock
        stats.small.stock = small_stock

        if stats.big.should_use(): # 大药可用
            # 设定点击位置
            click_roi = self.click_rois["big"]
            # 修改相应数量
            stats.big.usage += 1
            stats.big.stock -= 1
            # 构造反馈信息
            msg = stats.big.usage_report()
            # 设定后续节点
            next_node = "顺利完成吃药"
        elif stats.small.should_use(): # 小药可用
            click_roi = self.click_rois["small"]
            stats.small.usage += 1
            stats.small.stock -= 1
            msg = stats.small.usage_report()
            next_node = "顺利完成吃药"
        elif potion_type == "AP": 
            # 行动力恢复药不足，任务无法继续
            # 关闭恢复界面
            click_roi = self.click_rois["close"]
            # 设定结束跑图相关信息
            msg = f"行动力恢复药使用达到目标数量或库存不足,跑图任务结束"
            next_node = "AP药水不可用"
        else:
            # 战斗力恢复药不足,可放弃战斗，继续跑图。
            click_roi = self.click_rois["close"]
            msg = f"战斗力恢复药使用达到目标数量或库存不足,将放弃战斗继续跑图"
            next_node = "BC药水不可用"

        # 统一设定输出内容和后续走向
        common_func.dynamic_set_focus(context,target_node="输出恢复反馈",trigger="RECO_OK",focus_msg=msg)
        common_func.dynamic_set_next(context,pre_node="输出恢复反馈",next_node=next_node)
        logging.info(msg)
        return CustomRecognition.AnalyzeResult(box=click_roi, detail=msg)
        

        
