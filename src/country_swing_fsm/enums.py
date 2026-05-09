from enum import Enum


class Role(str, Enum):
    LEAD = "lead"
    FOLLOW = "follow"


class Direction(str, Enum):
    LEFT = "left"
    RIGHT = "right"


class PositionType(str, Enum):
    OPEN = "open"
    TWISTED = "twisted"
    ACCENT = "accent"


class MoveType(str, Enum):
    BASIC = "basic" # Idea: Basic (includes Basic Check Left / Basic Check Right, Stretch, Cuddle)
    SPICED_UP ="spiced_up" # Idea: Spicy (includes Hammerlock, arm slides, reverse sweetheart stuff)
    ROTATE = "rotate"
    CROSSED_ESCAPE = "crossed_escape"
    OFFER_OR_DROP = "offer_or_drop"
    ACCENT = "accent"
