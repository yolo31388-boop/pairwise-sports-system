"""
pairwise-sports-system - SportsSystem

This module contains a deliberately broken implementation.
Fix all bugs so that tests pass.
"""


class SportsSystem:
    def __init__(self):
        self.state = {}

    def calculate_ball_physics(self, *args, **kwargs):
        """BUG: 球物理不做空气阻力，永远匀速直线飞"""
        return None

    def update_player_physics(self, *args, **kwargs):
        """BUG: 球员物理不做碰撞，直接穿过去"""
        return None

    def check_game_rules(self, *args, **kwargs):
        """BUG: 比赛规则不做出界，球出界不吹"""
        return None

    def update_ai_player(self, *args, **kwargs):
        """BUG: AI不做战术，永远自己带"""
        return None

    def update_score(self, *args, **kwargs):
        """BUG: 计分不做验证，进了不算"""
        return None

