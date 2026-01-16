# input: 暂无
# output: 为 recover_action 和 recover_reco 提供药水数据管理.
# pos: 这里用来管理节点使用的数据

from dataclasses import dataclass,field
from typing import Tuple

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

    def get_status(self):
        """返回当前的药品状态数据"""
        data = {
            "name": self.name,
            "stock": self.stock,
            "usage": self.usage,
            "limit": self.limit
        }
        return data  # 把这个打包好的数据包扔回去
    
    def usage_report(self):
        """构造可以直接显示给用户的单次使用报告"""
        msg = f"使用第 {self.usage}/{self.limit} 瓶 {self.name},剩余库存量 {self.stock}"
        return msg
    
    def should_use(self):
        """判断当前这种药品是否可用"""
        if self.stock==0 or self.limit ==0: # 没有库存或者设置为不使用
            return False
        elif self.usage >= self.limit: # 使用数量超过限制
            return False
        else:
            return True


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

    # 是否使用免费恢复
    use_free_recover:bool = True

    def __post_init__(self):
        """
        初始化各种设置。

        【知识点】
        __post_init__ 是 dataclass 的魔法方法。
        当 PotionManager() 被创建完，所有变量初始化后，Python 会自动执行这个方法。
        """

        # 给每个药水取名
        self.ap.big.name = "大行动力恢复药"
        self.ap.small.name = "小行动力恢复药"
        self.bc.big.name = "大战斗力恢复药"
        self.bc.small.name = "小战斗力恢复药"

    def reset_usage(self):
        """清除所有药品使用量,用于手动重置。"""
        self.ap.reset_usage()
        self.bc.reset_usage()

# 创建总管
potion_stats = PotionManager()
