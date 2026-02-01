from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context
from . import lab_manager
import logging

@AgentServer.custom_recognition("find_4_star_filter")
class Find4StarFilter(CustomRecognition):
    """
    遍历四个筛选框，找到没有被点亮的筛选框，返回 ROI 值以供点击
    """
    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        to_click_list = []
        # 遍历字典中的每一个配置
        # name 是键 (例如 "filter_hide_deployed")
        # roi 是值 (例如 [1136, 298, 15, 14])
        for name, roi in lab_manager.batch_select_rois:
            reco_detail = context.run_recognition(
                "LabFilter",
                argv.image,
                {
                    "LabFilter": {
                        "roi": roi
                    }
                }
            )
            if not reco_detail or not reco_detail.hit:
                logging.info(f"[{argv.node_name}] 筛选按钮 {name} 未激活，加入点击列表。")
                to_click_list.append({
                    "name": name,
                    "roi": roi
                })
            else:
                logging.info(f"[{argv.node_name}] 筛选按钮 {name} 已勾选。")

            return CustomRecognition.AnalyzeResult(
                box=[0, 0, 0, 0],
                detail={
                    "click_targets": to_click_list
                }
            )