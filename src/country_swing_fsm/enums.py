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
    ACCENT_DIP = "accent_dip"
    ACCENT_OTHER = "accent_other"


class MoveType(str, Enum):
    BASIC = "basic" 
    SPICY ="spicy"
    ROTATE = "rotate"
    CROSSED_ESCAPE = "crossed_escape"
    OFFER_OR_DROP = "offer_or_drop"
    ACCENT = "accent"
