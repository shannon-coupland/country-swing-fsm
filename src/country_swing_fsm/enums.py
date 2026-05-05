from enum import Enum


class Role(str, Enum):
    LEAD = "lead"
    FOLLOW = "follow"


class Direction(str, Enum):
    LEFT = "left"
    RIGHT = "right"
