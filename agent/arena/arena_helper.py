# input: 暂无
# output: 为 arena_action 和 arena_reco 提供竞技场数据管理。
# pos: 这里用来管理竞技场相关的数据。

from dataclasses import dataclass,field

@dataclass
class ArenaStats:
    """竞技场相关的数据"""
    current_points: int = 0
    target_points: int = 100
    win_count: int = 0
    loss_count: int = 0

    def reset_arena(self):
        """将所有竞技场相关数据重置为默认值。"""
        self.current_points = 0
        self.target_points = 100
        self.win_count = 0
        self.loss_count = 0

arena_stats = ArenaStats()