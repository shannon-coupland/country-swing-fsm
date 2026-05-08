from enum import Enum


class Role(str, Enum):
    LEAD = "lead"
    FOLLOW = "follow"


class Direction(str, Enum):
    LEFT = "left"
    RIGHT = "right"


class PositionType(str, Enum):
    NORMAL = "normal"
    TWISTED = "twisted"
    IMPACT = "impact"


class MoveType(str, Enum):
    TURN = "turn" # Idea: Basic (includes Basic Check Left / Basic Check Right, Stretch, Cuddle)
    SPICY_TURN="spicy_turn" # Idea: Spicy (includes Hammerlock, arm slides, reverse sweetheart stuff)
    ROTATE = "rotate"
    CROSSED_ESCAPE = "crossed_escape"
    OFFER_OR_DROP = "offer_or_drop"
    OTHER = "other" # Idea: Impact
