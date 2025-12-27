# -*- coding: utf-8 -*-
"""
recover_action.py
Author: Beginner Learning Project
Description: Custom actions for managing and using recovery potions (AP/BC)
"""

import json
from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context

# Import potion data manager from states module
from states import potion_stats


@AgentServer.custom_action("init_potion_data")
class InitPotionData(CustomAction):
    """Initialize potion usage data"""

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        print("=== Initializing potion data ===")

        # Reset usage counters for all potions
        potion_stats.ap.reset_usage()
        potion_stats.bc.reset_usage()

        print("AP small/big potion usage has been reset")
        print("BC small/big potion usage has been reset")

        return True


@AgentServer.custom_action("use_ap_potion")
class UseAPPotion(CustomAction):
    """Use AP (Action Points) recovery potion"""

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        print("=== Using AP recovery potion ===")

        # Get user-configured limits from parameters
        # Note: custom_action_param is a JSON string, needs parsing
        try:
            if argv.custom_action_param:
                params = json.loads(argv.custom_action_param)
                small_limit = params.get("small_ap_limit", 60)
                big_limit = params.get("big_ap_limit", 999)
            else:
                # Use default values if no parameters
                small_limit = 60
                big_limit = 999
        except Exception as e:
            print(f"Failed to parse parameters: {e}")
            small_limit = 60
            big_limit = 999

        # Business logic: decide which potion to use
        if potion_stats.ap.small.usage < small_limit:
            # Use small potion if limit not reached
            potion_stats.ap.small.inc_usage()
            print(f"Used small AP potion (count: {potion_stats.ap.small.usage}/{small_limit})")

            # TODO: Add actual screen click code here
            # context.controller.post_click(x, y).wait()

        elif potion_stats.ap.big.usage < big_limit:
            # Use big potion if small potion limit reached
            potion_stats.ap.big.inc_usage()
            print(f"Used big AP potion (count: {potion_stats.ap.big.usage}/{big_limit})")

            # TODO: Add actual screen click code here

        else:
            # Both potions exhausted
            print("WARNING: All AP potions exhausted!")
            return False

        return True


@AgentServer.custom_action("use_bc_potion")
class UseBCPotion(CustomAction):
    """Use BC (Battle Cost) recovery potion"""

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        print("=== Using BC recovery potion ===")

        # Parse parameters
        try:
            if argv.custom_action_param:
                params = json.loads(argv.custom_action_param)
                small_limit = params.get("small_bc_limit", 60)
                big_limit = params.get("big_bc_limit", 999)
            else:
                small_limit = 60
                big_limit = 999
        except Exception as e:
            print(f"Failed to parse parameters: {e}")
            small_limit = 60
            big_limit = 999

        # Business logic
        if potion_stats.bc.small.usage < small_limit:
            potion_stats.bc.small.inc_usage()
            print(f"Used small BC potion (count: {potion_stats.bc.small.usage}/{small_limit})")
            return True

        elif potion_stats.bc.big.usage < big_limit:
            potion_stats.bc.big.inc_usage()
            print(f"Used big BC potion (count: {potion_stats.bc.big.usage}/{big_limit})")
            return True

        else:
            print("WARNING: All BC potions exhausted!")
            return False


@AgentServer.custom_action("show_potion_stats")
class ShowPotionStats(CustomAction):
    """Display current potion usage statistics"""

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        print("\n" + "="*50)
        print("Potion Usage Statistics")
        print("="*50)
        print(f"AP small potion: {potion_stats.ap.small.usage} used")
        print(f"AP big potion: {potion_stats.ap.big.usage} used")
        print(f"BC small potion: {potion_stats.bc.small.usage} used")
        print(f"BC big potion: {potion_stats.bc.big.usage} used")
        print("="*50 + "\n")

        return True
