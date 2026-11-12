"""Importing the installed distribution registers both LeRobot devices. No hardware I/O."""

from .config_nexarm import NexArmFollowerConfig, NexArmLeaderConfig
from .nexarm_follower import NexArmFollower
from .nexarm_leader import NexArmLeader

__all__ = ["NexArmFollower", "NexArmFollowerConfig", "NexArmLeader", "NexArmLeaderConfig"]
