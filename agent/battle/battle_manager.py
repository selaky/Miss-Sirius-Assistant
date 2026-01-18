# input: 暂无
# output: 为 battle_reco 和 battle_action 提供数据管理
# pos: 管理当前感染者和全部感染者信息库的相关数据

from dataclasses import dataclass,field

# --- 常量定义区 ---

# 具体的小类标识（对应放生清单里的复选框）
CAT_GENERAL = "一般"
CAT_BLUE = "蓝狼"
CAT_PINK = "粉狼"
CAT_RED = "红狼"

# 状态标识
MODE_NORMAL = "普通"
MODE_RAMPAGE = "暴走"

# 大类标识（卡组配置只关心这个）
GROUP_GENERAL = "General_Group"  # 一般感染者大类
GROUP_SIRIUS = "Sirius_Group"    # 天狼星大类

# 映射关系：具体小类 -> 大类
# 程序查到是"蓝狼"时，通过这个字典知道它属于"天狼星大类"
CATEGORY_TO_GROUP = {
    CAT_GENERAL: GROUP_GENERAL,
    CAT_BLUE:    GROUP_SIRIUS,
    CAT_PINK:    GROUP_SIRIUS,
    CAT_RED:     GROUP_SIRIUS
}

# 映射关系：OCR名字 -> 具体小类 (保持之前的逻辑)
ENEMY_NAME_MAP = {
    "天狼星": CAT_BLUE,       
    "超级天狼星": CAT_PINK,
    "终极天狼星": CAT_RED
    # 没在字典里的默认归为 CAT_GENERAL
}

# --- 结果标识 ---
RESULT_WIN = "胜利"
RESULT_RELEASE = "放生"

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
        # 这是一个映射字典，把中文状态映射到类里面的属性
        # 注意：这里存的是属性对象本身（引用），修改它就是修改类里的数据
        mapper = {
            "普通":self.normal_mode,
            "暴走":self.rampage_mode
        }
        # 如果是未知的状态，这里要处理一下，或者直接报错
        if mode_str not in mapper:
             raise ValueError(f"未知的状态: {mode_str}，代码逻辑可能有误")
        return mapper[mode_str]

def determine_category(name_str):
    """
    根据OCR出来的名字，查表返回对应的小类（蓝狼/红狼等）
    """
    # get(key, default) 方法：如果查不到，就返回默认值 CAT_GENERAL
    return ENEMY_NAME_MAP.get(name_str, CAT_GENERAL)


# 准备一个字典放所有敌人信息
archives = {}

active_context = EncounterContext()

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
    # 这里用一个集合(Set)来存。
    # 只有出现在集合里的 (类别, 状态) 组合，才会被放生。
    # 例如：{ ("蓝狼", "普通"), ("红狼", "暴走") }
    release_targets: set[tuple[str, str]] = field(default_factory=set)

    def set_release(self, category: str, mode: str, enable: bool):
        """
        供 UI 调用的辅助函数：切换某个选项的放生开关
        """
        target = (category, mode)
        if enable:
            self.release_targets.add(target)
        else:
            # discard 比 remove 安全，删除不存在的元素不会报错
            self.release_targets.discard(target)

# 实例化全局配置对象
current_config = UserBattleConfig()

@dataclass
class BattleAction:
    deck_name: str         # 这次战斗用哪个名字的卡组
    is_release_op: bool    # 打完是否需要执行放生操作 (True/False)


def get_battle_action(name: str, mode: str) -> BattleAction:
    """
    输入：OCR识别的名字 ("超级天狼星"), 状态 ("暴走")
    输出：战斗行动指令
    """
    # 1. 第一步：查户口，确定具体分类
    # 如果名字在映射表里，取对应分类，否则就是一般
    category = ENEMY_NAME_MAP.get(name, CAT_GENERAL)
    
    # 2. 第二步：判断是否触发放生 (最高优先级)
    # 检查 (类别, 状态) 是否在用户的放生清单集合里
    if (category, mode) in current_config.release_targets:
        # 命中放生！直接返回放生配置
        return BattleAction(
            deck_name=current_config.deck_release, # 替换为放生卡组
            is_release_op=True                     # 标记需要放生
        )
    
    # 3. 第三步：如果没有放生，根据大类选择常规卡组
    # 先查这个具体分类属于哪个大类 (一般组 还是 天狼星组)
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
        is_release_op=False # 不需要放生
    )



def reset_enemy_data():
    # 1. 声明我们要修改全局变量 active_context
    global active_context
    
    # 2. 清空历史记录字典
    # 使用 clear() 方法是原地清空，比重新赋值更安全
    archives.clear()
    
    # 3. 重置当前敌人信息
    # 直接创建一个新的实例覆盖旧变量，利用 Dataclass 的默认值特性实现重置
    active_context = EncounterContext()

    return True

def update_encounter_context(name,mode,level):
    """
    遇到敌人后，先确认是否和上次是同一个敌人.
    如果不是同一个,录入当前敌人信息，并把本次战斗次数清空。
    如果是同一个,什么也不做。
    绝对不要在开始战斗的时候加战斗数量,点了开始战斗不代表战斗真的开始了，只有看到结算数据才说明真的战斗了。
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
    # 读作：Profile, get record by mode.
    target_record = profile.get_record_by_mode(mode)
    
    # 分支逻辑，根据传入的参数，决定如何记账
    if result_type == RESULT_WIN:
        # ------- 胜利时的逻辑 -------
        target_record.win += 1
        
        # 只有胜利时才结算之前的失败次数
        # 逻辑：如果现在 battle_count 是 1，说明通过了 1 次战斗（即本次）就赢了，loss 不加
        # 如果 battle_count 是 3，说明第 3 次赢了，前 2 次输了，loss + 2
        if active_context.battle_count > 0:
            target_record.loss += (active_context.battle_count - 1)
        
            
    elif result_type == RESULT_RELEASE:
        # ------- 放生时的逻辑 -------
        # 不看 battle_count，直接加放生次数
        target_record.release += 1
        
    else:
        # 传入类型不对,报错提醒
        raise ValueError(f"未知的归档类型: {result_type}")
    
    # 更新最大等级记录
    if active_context.level > target_record.max_level:
            target_record.max_level = active_context.level

    return True
        
