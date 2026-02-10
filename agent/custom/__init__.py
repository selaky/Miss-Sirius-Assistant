# 导入所有自定义模块，触发 @AgentServer 装饰器注册
from .general import general_action, general_reco
from .recover import recover_action, recover_reco
from .arena import arena_action, arena_reco
from .boss import boss_action, boss_reco
from .battle import battle_action, battle_reco
from .lab import lab_action, lab_reco

# ======== 性能诊断 (排查性能退化时取消注释) ========
# 第1行: 注册诊断探针（仅跑"性能诊断测试"任务时需要）
# 第2行: 启用性能监控（会自动 instrument 所有已注册的自定义识别/动作）
#
# from .diagnostic import diagnostic_reco
# from .diagnostic.perf_monitor import PerfMonitor; PerfMonitor.enable()
