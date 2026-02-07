# input: 无
# output: lab_action
# pos: 存放各种实验室 roi 还有其他信息

# 一二三星卡全选按钮
batch_select_rois = {
    "btn_select_1_star": [1152,428,63,14],
    "btn_select_2_star": [1152,467,64,15],
    "btn_select_3_star": [1153,507,64,15],
}

# 筛选按钮选择框
filter_rois = {
    "filter_hide_deployed":    [1136,298,15,14],
    "filter_hide_sirius":      [1135,328,15,14],
    "filter_hide_locked":      [1136,358,15,14],
    "filter_hide_high_rarity": [1135,388,15,14],
}
# 卡槽位置通常是有序的，不需要区分名字，用列表即可
# Index 0 代表第一张卡，Index 5 代表第六张卡
card_slots = [
    [536,186,50,55], # Slot 1
    [741,196,49,55], # Slot 2
    [944,184,49,55], # Slot 3
    [534,457,50,55], # Slot 4
    [747,457,49,55], # Slot 5
    [947,457,50,55], # Slot 6
]

# 标记当前正在执行的实验室任务模式
# 该变量的值为模式任务起点对应的节点名
# 会在运行时动态更新
current_mode = "开始低星实验"