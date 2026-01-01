# input: 暂无
# output: 为 recover_action 和 recover_reco 提供药水数据管理.
# pos: 这里用来管理节点使用的数据

from dataclasses import dataclass,field

@dataclass
class SinglePotion:
    """定义每种药水记录"""
    name: str = "未命名药品"
    usage: int = 0
    limit: int = 0
    stock: int = 0

    def reset_usage(self):
        """重置使用药水数"""
        self.usage = 0
    
    def inc_usage(self):
        """使用药水数量 +1"""
        self.usage += 1

    def get_status(self):
        """返回当前的药品状态数据"""
        data = {
            "name": self.name,
            "stock": self.stock,
            "usage": self.usage,
            "limit": self.limit
        }
        return data  # 把这个打包好的数据包扔回去


@dataclass
class PotionType:
    """定义大小药"""
    big: SinglePotion = field(default_factory=SinglePotion)
    small: SinglePotion = field(default_factory=SinglePotion)

    def reset_usage(self):
        """清除该类药品大药和小药的已使用量"""
        self.big.reset_usage()
        self.small.reset_usage()

    def set_limit(self,big_num,small_num):
        self.big.limit = big_num
        self.small.limit = small_num


@dataclass 
class PotionManager:
    """定义药水大类"""
    ap:PotionType = field(default_factory=PotionType)
    bc:PotionType = field(default_factory=PotionType)

    def init_names(self):
        """给每个药水取名"""
        self.ap.big.name = "大行动力恢复药"
        self.ap.small.name = "小行动力恢复药"
        self.bc.big.name = "大战斗力恢复药"
        self.bc.small.name = "小战斗力恢复药"

    def reset_usage(self):
        """清除所有药品使用量"""
        self.ap.reset_usage()
        self.bc.reset_usage()

# 创建总管
potion_stats = PotionManager()

# 初始化所有药水名字
potion_stats.init_names()

def node_name_extract(node_name):
    """
    节点名称解析.通过调用的节点名字来判断当前要处理的药品是哪一类。
    识别方法是看节点名字中出现了 AP 还是 BC, 以及是大还是小。
    """
    if ("AP" in node_name):
        if ("大" in node_name):
            return potion_stats.ap.big
        elif ("小" in node_name):
            return potion_stats.ap.small
        else:
            raise ValueError(f"致命错误：在名称 '{node_name}' 中未识别出药品规格(大/小)！请确保你在正确的节点调用此动作或识别，并且对节点规范命名。")
    elif ("BC" in node_name):
        if ("大" in node_name):
            return potion_stats.bc.big
        elif ("小" in node_name):
            return potion_stats.bc.small
        else:
            raise ValueError((f"致命错误：在名称 '{node_name}' 中未识别出药品种类(AP/BC)！请确保你在正确的节点调用此动作或识别，并且对节点规范命名。"))
