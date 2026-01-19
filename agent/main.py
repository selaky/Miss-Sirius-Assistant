import sys
import os
import logging

# 将脚本所在目录添加到模块搜索路径，确保能找到同目录下的模块
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from maa.agent.agent_server import AgentServer
from maa.toolkit import Toolkit

import my_action
import my_reco
from recover import recover_action
from recover import recover_reco
from arena import arena_action
from arena import arena_reco
from boss import boss_action
from boss import boss_reco
from utils import common_action
from utils import common_reco
from battle import battle_action,battle_reco


def main():
    logging.basicConfig(level=logging.INFO) # 输出日志，看看情况。

    Toolkit.init_option("./")

    if len(sys.argv) < 2:
        print("Usage: python main.py <socket_id>")
        print("socket_id is provided by AgentIdentifier.")
        sys.exit(1)
        
    socket_id = sys.argv[-1]

    AgentServer.start_up(socket_id)
    AgentServer.join()
    AgentServer.shut_down()


if __name__ == "__main__":
    main()
