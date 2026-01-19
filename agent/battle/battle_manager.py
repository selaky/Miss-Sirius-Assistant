# input: 暂无
# output: 为 battle_reco 和 battle_action 提供数据管理
# pos: 管理当前感染者和全部感染者信息库的相关数据

# ==========================================
# 1. 库与模块导入区 (Imports)
# ==========================================
from dataclasses import dataclass, field

# ==========================================
# 2. 常量与配置映射区 (Constants & Mappings)
# ==========================================
# --- 基础标识 ---
CAT_GENERAL = "一般"
CAT_BLUE = "蓝狼"
CAT_PINK = "粉狼"
CAT_RED = "红狼"

MODE_NORMAL = "普通"
MODE_RAMPAGE = "暴走"

GROUP_GENERAL = "General_Group"  # 一般感染者大类
GROUP_SIRIUS = "Sirius_Group"    # 天狼星大类

RESULT_WIN = "胜利"
RESULT_RELEASE = "放生"

# --- 映射关系表 ---
# 映射关系：具体小类 -> 大类
CATEGORY_TO_GROUP = {
    CAT_GENERAL: GROUP_GENERAL,
    CAT_BLUE:    GROUP_SIRIUS,
    CAT_PINK:    GROUP_SIRIUS,
    CAT_RED:     GROUP_SIRIUS
}

# 映射关系：OCR名字 -> 具体小类
ENEMY_NAME_MAP = {
    "天狼星": CAT_BLUE,       
    "超级天狼星": CAT_PINK,
    "终极天狼星": CAT_RED
    # 没在字典里的默认归为 CAT_GENERAL
}

# 战斗卡组 ROI
# 分辨率缩放由框架解决,这里只负责 ROI 本身
BATTLE_ROI = {
    "卡组一": [1187,96,66,54],
    "卡组二": [1186,193,68,63],
    "卡组三": [1188,296,66,57],
    "卡组四": [1185,392,72,60]
}

# ==========================================
# 3. 数据模型定义区 (Data Classes)
# ==========================================
# 定义数据的"形状"，这里只定义类，不创建具体的对象

@dataclass
class EncounterContext:
    # 最近一次遭遇的感染者信息
    name: str = "未知感染者" # 名字
    mode: str = "普通" # 普通/暴走
    category: str = "一般" # 一般/狼
    level: int = 0 # 等级
    battle_count: int = 0 # 与同一个感染者已经战斗的次数

@dataclass
class CombatRecord:    
    # 单个状态下的感染者历史信息
    max_level: int = 0
    win: int = 0
    loss: int = 0
    release:int = 0

@dataclass
class EnemyProfile:
    # 本次程序运行期间，所有已遭遇感染者信息
    name: str = "未知感染者"
    # 使用 default_factory 确保每个敌人都有独立的统计数据对象，不混用
    normal_mode: CombatRecord = field(default_factory=CombatRecord)
    rampage_mode: CombatRecord = field(default_factory=CombatRecord)
        
    def get_record_by_mode(self, mode_str: str) -> CombatRecord:
        """
        核心魔法：根据传入的字符串（"普通"/"暴走"），并不是去判断，
        而是查表，直接把对应的内部对象交出去。
        """
        mapper = {
            "普通":self.normal_mode,
            "暴走":self.rampage_mode
        }
        if mode_str not in mapper:
             raise ValueError(f"未知的状态: {mode_str}，代码逻辑可能有误")
        return mapper[mode_str]

@dataclass
class BattleStrategy:
    """
    单种敌人在单种状态下的战斗策略
    """
    deck_name: str = "卡组一"  # 默认用卡组一
    allow_release: bool = False # 默认不放生

@dataclass
class UserBattleConfig:
    # --- 1. 卡组配置 (对应界面的5个下拉框) ---
    deck_general_normal: str = "卡组一"
    deck_general_rampage: str = "卡组一"
    
    deck_sirius_normal: str = "卡组一"
    deck_sirius_rampage: str = "卡组一"
    
    # 单独的放生卡组
    deck_release: str = "卡组一" 

    # --- 2. 放生清单 (对应界面的复选框) ---
    release_targets: set[tuple[str, str]] = field(default_factory=set)

    # --- 3. 公屏信息 (对应输入框) ---
    broadcast = False
    broadcast_addition: str = ""

    def set_release(self, category: str, mode: str, enable: bool):
        """
        供 UI 调用的辅助函数：切换某个选项的放生开关
        """
        target = (category, mode)
        if enable:
            self.release_targets.add(target)
        else:
            self.release_targets.discard(target)

    

@dataclass
class BattleAction:
    deck_name: str         # 这次战斗用哪个名字的卡组
    is_release_op: bool    # 打完是否需要执行放生操作 (True/False)

# ==========================================
# 4. 全局状态实例化区 (Global Instances)
# ==========================================
# 创建实际存储数据的容器，上面的类是图纸，这里是盖好的房子

# 准备一个字典放所有敌人信息
archives = {}

# 当前正在战斗的上下文
active_context = EncounterContext()

# 实例化全局配置对象
current_config = UserBattleConfig()

# 配置是否已初始化的标志（必须通过战斗设置任务来设置）
is_configured = False

# ==========================================
# 5. 核心逻辑函数区 (Core Logic Functions)
# ==========================================

def determine_category(name_str):
    """
    根据OCR出来的名字，查表返回对应的小类（蓝狼/红狼等）
    """
    return ENEMY_NAME_MAP.get(name_str, CAT_GENERAL)

def reset_enemy_data():
    global active_context
    # 清空历史记录字典
    archives.clear()
    # 重置当前敌人信息
    active_context = EncounterContext()
    return True

def update_encounter_context(name, mode, level):
    """
    遇到敌人后，先确认是否和上次是同一个敌人.
    如果不是同一个,录入当前敌人信息，并把本次战斗次数清空。
    """
    # 判断是否和上次敌人名字、状态和等级都相同
    if name == active_context.name and mode == active_context.mode and level == active_context.level:
        return True
    else:
        # 更新已知信息
        active_context.name = name
        active_context.mode = mode
        active_context.level = level
        # 根据名字判断种类
        active_context.category = determine_category(name)
        # 重置战斗次数
        active_context.battle_count = 0
        return True

def get_battle_action(name: str, mode: str) -> BattleAction:
    """
    输入：OCR识别的名字 ("超级天狼星"), 状态 ("暴走")
    输出：战斗行动指令
    """
    # 1. 第一步：查户口，确定具体分类
    category = ENEMY_NAME_MAP.get(name, CAT_GENERAL)
    
    # 2. 第二步：判断是否触发放生 (最高优先级)
    if (category, mode) in current_config.release_targets:
        return BattleAction(
            deck_name=current_config.deck_release, 
            is_release_op=True                     
        )
    
    # 3. 第三步：如果没有放生，根据大类选择常规卡组
    group = CATEGORY_TO_GROUP.get(category, GROUP_GENERAL)
    
    if group == GROUP_GENERAL:
        if mode == MODE_NORMAL:
            target_deck = current_config.deck_general_normal
        else:
            target_deck = current_config.deck_general_rampage
            
    elif group == GROUP_SIRIUS:
        if mode == MODE_NORMAL:
            target_deck = current_config.deck_sirius_normal
        else:
            target_deck = current_config.deck_sirius_rampage
            
    # 返回常规战斗指令
    return BattleAction(
        deck_name=target_deck,
        is_release_op=False 
    )

def archive_battle_result(result_type):
    """
    通用归档函数：根据 result_type (胜利/放生) 来分别处理数据。
    """
    # 从活跃上下文里取名字
    name = active_context.name
    mode = active_context.mode
    
    # 懒加载：如果档案馆里没这个人，先建个档案
    if name not in archives:
        archives[name] = EnemyProfile(name=name)
    
    # 取出档案
    profile = archives[name]
    # 根据当前模式，拿到对应的战绩卡
    target_record = profile.get_record_by_mode(mode)
    
    # 分支逻辑，根据传入的参数，决定如何记账
    if result_type == RESULT_WIN:
        # ------- 胜利时的逻辑 -------
        target_record.win += 1
        
        # 只有胜利时才结算之前的失败次数
        if active_context.battle_count > 0:
            target_record.loss += (active_context.battle_count - 1)
        
    elif result_type == RESULT_RELEASE:
        # ------- 放生时的逻辑 -------
        target_record.release += 1
        
    else:
        raise ValueError(f"未知的归档类型: {result_type}")
    
    # 更新最大等级记录
    if active_context.level > target_record.max_level:
            target_record.max_level = active_context.level

    return True

# ==========================================
# 6. 配置设置函数区 (Config Setters)
# ==========================================
# 供 action 调用的配置设置函数

def set_config_value(key: str, value) -> bool:
    """
    通用配置设置函数：根据 key 设置对应的配置项

    Args:
        key: 配置项的键名
        value: 配置项的值

    Returns:
        bool: 设置是否成功
    """
    global is_configured

    # 卡组配置映射
    deck_keys = {
        "deck_general_normal": "deck_general_normal",
        "deck_general_rampage": "deck_general_rampage",
        "deck_sirius_normal": "deck_sirius_normal",
        "deck_sirius_rampage": "deck_sirius_rampage",
        "deck_release": "deck_release",
    }

    # 放生配置映射 (category, mode)
    release_keys = {
        "release_general_normal": (CAT_GENERAL, MODE_NORMAL),
        "release_general_rampage": (CAT_GENERAL, MODE_RAMPAGE),
        "release_blue_normal": (CAT_BLUE, MODE_NORMAL),
        "release_blue_rampage": (CAT_BLUE, MODE_RAMPAGE),
        "release_pink_normal": (CAT_PINK, MODE_NORMAL),
        "release_pink_rampage": (CAT_PINK, MODE_RAMPAGE),
        "release_red_normal": (CAT_RED, MODE_NORMAL),
        "release_red_rampage": (CAT_RED, MODE_RAMPAGE),
    }

    if key in deck_keys:
        # 设置卡组配置
        setattr(current_config, deck_keys[key], value)
        return True

    elif key in release_keys:
        # 设置放生配置
        category, mode = release_keys[key]
        enable = str(value).lower() in ("true", "1", "yes")
        current_config.set_release(category, mode, enable)
        return True

    elif key == "broadcast":
        # 设置公屏发送开关
        current_config.broadcast = str(value).lower() in ("true", "1", "yes")
        return True

    elif key == "broadcast_addition":
        # 设置公屏附加信息
        current_config.broadcast_addition = str(value) if value else ""
        return True

    elif key == "enable_release":
        # 放生总开关（如果关闭，清空所有放生目标）
        enable = str(value).lower() in ("true", "1", "yes")
        if not enable:
            current_config.release_targets.clear()
        return True

    elif key == "mark_configured":
        # 标记配置完成
        is_configured = True
        return True

    else:
        raise ValueError(f"未知的配置项: {key}")

def get_config_summary() -> str:
    """
    获取当前配置的摘要信息，用于日志输出
    """
    lines = [
        "=== 战斗配置摘要 ===",
        f"一般普通卡组: {current_config.deck_general_normal}",
        f"一般暴走卡组: {current_config.deck_general_rampage}",
        f"天狼星普通卡组: {current_config.deck_sirius_normal}",
        f"天狼星暴走卡组: {current_config.deck_sirius_rampage}",
        f"放生卡组: {current_config.deck_release}",
        f"放生目标: {current_config.release_targets if current_config.release_targets else '无'}",
        f"公屏发送: {'开启' if current_config.broadcast else '关闭'}",
    ]
    if current_config.broadcast:
        lines.append(f"公屏附加信息: {current_config.broadcast_addition or '(空)'}")
    lines.append("==================")
    return "\n".join(lines)

def check_configured() -> bool:
    """
    检查战斗配置是否已完成初始化
    """
    return is_configured
