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

    def print_information(self):
        """打印这类药品的信息"""
        print(f"{name}库存:{self.stock}")
        print(f"{name}已用:{self.usage}")
        print(f"{name}限制:{self.limit}")

@dataclass
class PotionType:
    """定义大小药"""
    big: SinglePotion = field(default_factory=SinglePotion)
    small: SinglePotion = field(default_factory=SinglePotion)

    def reset_usage(self):
        """清除该类药品大药和小药的已使用量"""
        self.big.reset_usage()
        self.small.reset_usage()


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

# 创建总管
potion_stats = PotionManager()

# 初始化所有药水名字
potion_stats.init_names()