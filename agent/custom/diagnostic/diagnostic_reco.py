# 诊断探针 - 用于快速复现性能退化的测试用自定义识别
#
# 配合 assets/resource/pipeline/诊断测试.json 使用。
# 该探针始终返回"匹配"，使 pipeline 形成快速循环，
# 在短时间内积累大量节点来触发性能退化。
#
# 用法:
#   1. 在 custom/__init__.py 中取消注释 diagnostic 相关导入
#   2. 在通用 UI 中选择"性能诊断测试"任务并运行
#   3. 观察日志中节点数与耗时的关系

import time

from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context

from utils.logger import logger


@AgentServer.custom_recognition("perf_probe")
class PerfProbe(CustomRecognition):
    """
    诊断探针: 始终返回匹配，用于在循环中测量回调开销。

    参数 (通过 custom_recognition_param 传入):
        max_iterations: 最大迭代次数，达到后返回 None 停止循环 (默认 3000)
        log_interval:   每 N 次迭代输出一条探针日志 (默认 100)
    """

    _call_count = 0
    _start_time = 0

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:

        PerfProbe._call_count += 1
        count = PerfProbe._call_count

        if count == 1:
            PerfProbe._start_time = time.time()

        # 解析参数
        max_iter = 3000
        log_interval = 100
        if argv.custom_recognition_param:
            try:
                import json
                params = json.loads(argv.custom_recognition_param)
                max_iter = int(params.get("max_iterations", 3000))
                log_interval = int(params.get("log_interval", 100))
            except Exception:
                pass

        # 达到上限，停止循环
        if count > max_iter:
            elapsed = time.time() - PerfProbe._start_time
            logger.info(
                f"[PerfProbe] 测试完成! 共 {count - 1} 次迭代, "
                f"耗时 {elapsed:.1f} 秒"
            )
            PerfProbe._call_count = 0
            return CustomRecognition.AnalyzeResult(box=None, detail="测试完成")

        # 定期输出进度
        if count % log_interval == 0:
            elapsed = time.time() - PerfProbe._start_time
            rate = count / elapsed if elapsed > 0 else 0
            logger.info(
                f"[PerfProbe] 第 {count}/{max_iter} 次 | "
                f"已运行 {elapsed:.1f}s | 速率 {rate:.1f} 次/秒"
            )

        # 始终返回匹配，保持循环继续
        return CustomRecognition.AnalyzeResult(
            box=(0, 0, 1, 1),
            detail=f"probe #{count}"
        )
