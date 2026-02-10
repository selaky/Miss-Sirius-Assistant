# 性能诊断模块 - 用于排查长时间运行后自定义识别/动作变慢的问题
#
# 原理:
#   通过 monkey-patch MAA SDK 的关键方法，在不修改任何业务代码的情况下
#   自动收集每次回调的性能数据，包括:
#   - get_task_detail() 耗时和返回的节点数 (疑似根因)
#   - run_recognition() 每次 IPC 调用耗时
#   - 用户代码本身的耗时
#   - 进程内存使用
#
# 使用方法:
#   在 agent/custom/__init__.py 末尾添加:
#       from .diagnostic.perf_monitor import PerfMonitor
#       PerfMonitor.enable()
#
#   然后正常运行任务即可，观察日志中 [Perf] 前缀的输出。
#   诊断完成后注释掉那两行即可关闭。

import time
import gc
import ctypes
import functools
from collections import deque

from utils.logger import logger


class PerfMonitor:
    """
    性能监控器

    通过 monkey-patch SDK 内部方法来收集性能指标。
    所有状态都是类变量，不需要实例化。
    """

    _enabled = False

    # ===== 每次回调期间的临时状态 =====
    # 这些值由 monkey-patch 的 SDK 方法在回调过程中写入，
    # 由包装后的用户方法读取。因为 Agent Server 是单线程的，所以线程安全。
    _cb_gtd_ms = 0.0           # get_task_detail 耗时 (ms)
    _cb_node_count = 0          # get_task_detail 返回的节点数
    _cb_gnd_count = 0           # get_node_detail 调用次数 (在 get_task_detail 内部)
    _cb_grd_ms = 0.0            # get_recognition_detail 耗时 (仅 action 回调的前置调用)
    _cb_reco_calls = []         # 用户代码中 run_recognition 调用记录 [(name, ms), ...]
    _inside_gtd = False         # 标记: 当前是否在 get_task_detail 内部

    # ===== 统计数据 =====
    _total_calls = 0
    _summary_interval = 20      # 每 N 次回调输出一次摘要
    _history = deque(maxlen=500)  # 最近 500 条记录
    _start_time = 0

    @classmethod
    def enable(cls):
        """启用性能监控，monkey-patch SDK 方法并包装所有已注册的回调"""
        if cls._enabled:
            return
        cls._enabled = True
        cls._start_time = time.time()

        # 按顺序 patch，确保依赖关系正确
        cls._patch_get_task_detail()
        cls._patch_get_node_detail()
        cls._patch_get_recognition_detail()
        cls._patch_run_recognition()
        cls._wrap_all_callbacks()

        logger.info("=" * 60)
        logger.info("[Perf] 性能诊断模块已启用")
        logger.info("[Perf] 疑似根因: SDK 每次回调无条件调用 get_task_detail()")
        logger.info("[Perf]           该方法遍历所有历史节点，复杂度 O(N)")
        logger.info("[Perf] 关注指标: 节点数(nodes) 与 SDK耗时(sdk_ms) 是否正相关")
        logger.info("=" * 60)

    # ===== 内存测量 =====

    @classmethod
    def _get_memory_mb(cls) -> float:
        """获取当前进程的工作集内存 (MB)"""
        try:
            # 优先使用 psutil
            import psutil
            return psutil.Process().memory_info().rss / 1024 / 1024
        except ImportError:
            pass
        # Windows 备用方案
        try:
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                    ("PrivateUsage", ctypes.c_size_t),
                ]

            counters = PROCESS_MEMORY_COUNTERS_EX()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
            psapi = ctypes.windll.psapi
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return counters.WorkingSetSize / 1024 / 1024
        except Exception:
            pass
        return -1

    # ===== Monkey-Patch SDK 方法 =====

    @classmethod
    def _patch_get_task_detail(cls):
        """patch Tasker.get_task_detail: 记录耗时和节点数"""
        from maa.tasker import Tasker
        _orig = Tasker.get_task_detail

        @functools.wraps(_orig)
        def patched(self, task_id):
            # 重置本次回调的临时状态
            cls._cb_grd_ms = 0
            cls._cb_reco_calls = []
            cls._cb_gnd_count = 0
            cls._inside_gtd = True

            t0 = time.perf_counter()
            result = _orig(self, task_id)
            ms = (time.perf_counter() - t0) * 1000

            cls._inside_gtd = False
            cls._cb_gtd_ms = ms
            cls._cb_node_count = len(result.nodes) if result and result.nodes else 0
            return result

        Tasker.get_task_detail = patched

    @classmethod
    def _patch_get_node_detail(cls):
        """patch Tasker.get_node_detail: 统计在 get_task_detail 内部的调用次数"""
        from maa.tasker import Tasker
        _orig = Tasker.get_node_detail

        @functools.wraps(_orig)
        def patched(self, node_id):
            result = _orig(self, node_id)
            if cls._inside_gtd:
                cls._cb_gnd_count += 1
            return result

        Tasker.get_node_detail = patched

    @classmethod
    def _patch_get_recognition_detail(cls):
        """patch Tasker.get_recognition_detail: 记录 action 回调前置调用的耗时"""
        from maa.tasker import Tasker
        _orig = Tasker.get_recognition_detail

        @functools.wraps(_orig)
        def patched(self, reco_id):
            t0 = time.perf_counter()
            result = _orig(self, reco_id)
            ms = (time.perf_counter() - t0) * 1000
            # 只记录不在 get_task_detail 内部的调用
            if not cls._inside_gtd:
                cls._cb_grd_ms += ms
            return result

        Tasker.get_recognition_detail = patched

    @classmethod
    def _patch_run_recognition(cls):
        """patch Context.run_recognition: 记录用户代码中每次识别调用的耗时"""
        from maa.context import Context
        _orig = Context.run_recognition

        @functools.wraps(_orig)
        def patched(self, entry, image, pipeline_override={}):
            t0 = time.perf_counter()
            result = _orig(self, entry, image, pipeline_override)
            ms = (time.perf_counter() - t0) * 1000
            cls._cb_reco_calls.append((entry, round(ms, 1)))
            return result

        Context.run_recognition = patched

    # ===== 包装用户回调 =====

    @classmethod
    def _wrap_all_callbacks(cls):
        """包装所有已注册的自定义识别和动作，添加性能计时"""
        from maa.agent.agent_server import AgentServer

        # 包装自定义识别
        for name, reco in AgentServer._custom_recognition_holder.items():
            if hasattr(reco, '_perf_wrapped'):
                continue
            cls._wrap_recognition(name, reco)

        # 包装自定义动作
        for name, action in AgentServer._custom_action_holder.items():
            if hasattr(action, '_perf_wrapped'):
                continue
            cls._wrap_action(name, action)

    @classmethod
    def _wrap_recognition(cls, reco_name, reco_instance):
        """包装单个自定义识别的 analyze 方法"""
        original_analyze = reco_instance.__class__.analyze

        def make_wrapper(name, orig):
            @functools.wraps(orig)
            def wrapper(self, context, argv):
                # 此时 _cb_gtd_ms 和 _cb_node_count 已由 SDK patch 设置
                gtd_ms = cls._cb_gtd_ms
                node_count = cls._cb_node_count
                gnd_count = cls._cb_gnd_count
                cls._cb_reco_calls = []

                t0 = time.perf_counter()
                result = orig(self, context, argv)
                user_ms = (time.perf_counter() - t0) * 1000

                reco_calls = list(cls._cb_reco_calls)
                cls._emit_record(
                    cb_type="RECO",
                    cb_name=name,
                    node_name=argv.node_name,
                    gtd_ms=gtd_ms,
                    node_count=node_count,
                    gnd_count=gnd_count,
                    grd_ms=0,
                    user_ms=user_ms,
                    reco_calls=reco_calls,
                )
                return result
            return wrapper

        reco_instance.__class__.analyze = make_wrapper(reco_name, original_analyze)
        reco_instance._perf_wrapped = True

    @classmethod
    def _wrap_action(cls, action_name, action_instance):
        """包装单个自定义动作的 run 方法"""
        original_run = action_instance.__class__.run

        def make_wrapper(name, orig):
            @functools.wraps(orig)
            def wrapper(self, context, argv):
                gtd_ms = cls._cb_gtd_ms
                node_count = cls._cb_node_count
                gnd_count = cls._cb_gnd_count
                grd_ms = cls._cb_grd_ms
                cls._cb_reco_calls = []

                t0 = time.perf_counter()
                result = orig(self, context, argv)
                user_ms = (time.perf_counter() - t0) * 1000

                reco_calls = list(cls._cb_reco_calls)
                cls._emit_record(
                    cb_type="ACT",
                    cb_name=name,
                    node_name=argv.node_name,
                    gtd_ms=gtd_ms,
                    node_count=node_count,
                    gnd_count=gnd_count,
                    grd_ms=grd_ms,
                    user_ms=user_ms,
                    reco_calls=reco_calls,
                )
                return result
            return wrapper

        action_instance.__class__.run = make_wrapper(action_name, original_run)
        action_instance._perf_wrapped = True

    # ===== 输出 =====

    @classmethod
    def _emit_record(cls, cb_type, cb_name, node_name, gtd_ms, node_count,
                     gnd_count, grd_ms, user_ms, reco_calls):
        cls._total_calls += 1

        reco_total_ms = sum(ms for _, ms in reco_calls)
        pure_user_ms = user_ms - reco_total_ms  # 用户代码中去掉 run_recognition 的时间
        sdk_ms = gtd_ms + grd_ms
        total_ms = sdk_ms + user_ms
        mem_mb = cls._get_memory_mb()
        uptime_min = (time.time() - cls._start_time) / 60

        # 保存到历史
        cls._history.append({
            "n": cls._total_calls,
            "type": cb_type,
            "name": cb_name,
            "total": round(total_ms, 1),
            "sdk": round(sdk_ms, 1),
            "gtd": round(gtd_ms, 1),
            "grd": round(grd_ms, 1),
            "user": round(user_ms, 1),
            "reco": round(reco_total_ms, 1),
            "pure": round(pure_user_ms, 1),
            "nodes": node_count,
            "gnd": gnd_count,
            "mem": round(mem_mb, 1),
            "min": round(uptime_min, 1),
        })

        # 构建 run_recognition 的详情
        reco_str = ""
        if reco_calls:
            reco_str = " | 识别调用: " + ", ".join(
                f"{n}({m:.0f}ms)" for n, m in reco_calls
            )

        # 输出每次调用的日志
        logger.info(
            f"[Perf] #{cls._total_calls} [{cb_type}] {cb_name} | "
            f"总计={total_ms:.0f}ms "
            f"(SDK={sdk_ms:.0f}ms [gtd={gtd_ms:.0f} grd={grd_ms:.0f}] "
            f"用户={user_ms:.0f}ms [识别IPC={reco_total_ms:.0f} 纯逻辑={pure_user_ms:.0f}]) | "
            f"节点数={node_count} (展开{gnd_count}个) | "
            f"内存={mem_mb:.0f}MB | 运行{uptime_min:.1f}分钟"
            f"{reco_str}"
        )

        # SDK 开销超过 1 秒时额外警告
        if sdk_ms > 1000:
            logger.warning(
                f"[Perf] ⚠ SDK 开销严重! get_task_detail 耗时 {gtd_ms:.0f}ms, "
                f"展开了 {node_count} 个历史节点 ({gnd_count} 次 IPC)"
            )

        # 定期输出摘要
        if cls._total_calls % cls._summary_interval == 0:
            cls._print_summary()

    @classmethod
    def _print_summary(cls):
        """输出最近一段时间的性能趋势摘要"""
        if len(cls._history) < 4:
            return

        recent = list(cls._history)

        logger.info("=" * 70)
        logger.info(f"[Perf] ========== 性能趋势摘要 (第 {cls._total_calls} 次调用) ==========")

        # 找出 SDK 开销最大的记录
        by_sdk = sorted(recent, key=lambda r: r["gtd"], reverse=True)
        worst = by_sdk[0]
        best = by_sdk[-1]
        logger.info(
            f"[Perf] get_task_detail 最慢: {worst['gtd']:.0f}ms "
            f"(节点数={worst['nodes']}, 第{worst['n']}次, {worst['name']})"
        )
        logger.info(
            f"[Perf] get_task_detail 最快: {best['gtd']:.0f}ms "
            f"(节点数={best['nodes']}, 第{best['n']}次, {best['name']})"
        )

        # 节点数趋势
        first_nodes = recent[0]["nodes"]
        last_nodes = recent[-1]["nodes"]
        logger.info(
            f"[Perf] 节点数趋势: {first_nodes} → {last_nodes} "
            f"(+{last_nodes - first_nodes})"
        )

        # 内存趋势
        first_mem = recent[0]["mem"]
        last_mem = recent[-1]["mem"]
        if first_mem > 0 and last_mem > 0:
            logger.info(
                f"[Perf] 内存趋势: {first_mem:.0f}MB → {last_mem:.0f}MB "
                f"({last_mem - first_mem:+.0f}MB)"
            )

        # 相关性分析: 节点数与 SDK 耗时
        # 取节点数差异最大的两条记录看比率
        if last_nodes > first_nodes and last_nodes > 100:
            first_sdk = recent[0]["gtd"]
            last_sdk = recent[-1]["gtd"]
            if first_sdk > 0:
                ratio = last_sdk / first_sdk
                node_ratio = last_nodes / max(first_nodes, 1)
                logger.info(
                    f"[Perf] 相关性: 节点增长 {node_ratio:.1f}x, "
                    f"SDK耗时增长 {ratio:.1f}x "
                    f"{'→ 强相关! 确认为节点累积问题' if ratio > node_ratio * 0.5 else ''}"
                )

        # GC 状态
        gc_counts = gc.get_count()
        logger.info(
            f"[Perf] GC: gen0={gc_counts[0]} gen1={gc_counts[1]} gen2={gc_counts[2]}"
        )

        logger.info("=" * 70)
