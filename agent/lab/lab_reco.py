from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context
from . import lab_manager
import logging


@AgentServer.custom_recognition("check_lab_filter")
class CheckLabFilter(CustomRecognition):
    """
    遍历四个筛选框，找到没有被点亮的筛选框，返回 ROI 值以供点击.
    """

    # 定义两种期望状态配置
    # True 代表希望它亮着（勾选），False 代表希望它灭着（未勾选）

    # 打开所有筛选,目的是筛选出所有的四星卡。
    # 实际上此操作筛选出来的是四星及以下的所有卡，
    # 但是因为本识别会在一、二、三星卡全都进行实验之后执行，因此实际留下的只有四星
    FILTER_ALL_ON = {
        "filter_hide_deployed":    True,
        "filter_hide_sirius":      True,
        "filter_hide_locked":      True,
        "filter_hide_high_rarity": True,
    }

    # 只有 sirius 不同：天狼星我们希望能看到（即取消隐藏/取消勾选）
    FILTER_SIRIUS_OFF = {
        "filter_hide_deployed":    True,
        "filter_hide_sirius":      False,
        "filter_hide_locked":      True,
        "filter_hide_high_rarity": False,
    }

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        to_click_list = []

        # 确认当前在哪个模式
        if "四星" in argv.node_name:
            target_config = self.FILTER_ALL_ON
        elif "天狼星" in argv.node_name:
            target_config = self.FILTER_SIRIUS_OFF
        else:
            raise ValueError(f"[{argv.node_name}] 严重错误:未在节点名称中找到\"四星\"/\"天狼星\".请确保节点名称正确且在正确的节点调用此识别")

        # 遍历字典中的每一个配置
        # name 是键 (例如 "filter_hide_deployed")
        # roi 是值 (例如 [1136, 298, 15, 14])
        for name, roi in lab_manager.filter_rois.items():
            # 取出此处期望的勾选/取消状态
            # 这里故意不使用 `get` 来使用默认值，防止配置漏写无法发现
            expected_state = target_config[name]
            reco_detail = context.run_recognition(
                "LabFilter",
                argv.image,
                {
                    "LabFilter": {
                        "roi": roi
                    }
                }
            )

            current_state = False
            if reco_detail and reco_detail.hit:
                current_state = True
            # --- 当前 != 期望，则需要点击 ---
            if current_state != expected_state:
                action = "勾选" if expected_state else "取消"
                logging.info(f"[{argv.node_name}] 按钮 {name} 当前状态({current_state})不符合期望({expected_state})，加入点击列表以执行{action}。")
                
                to_click_list.append({
                    "name": name,
                    "roi": roi
                })

        return CustomRecognition.AnalyzeResult(
            box=[0, 0, 0, 0],
            detail={
                "click_targets": to_click_list
            }
        )