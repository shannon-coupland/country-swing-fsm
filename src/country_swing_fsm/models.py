from __future__ import annotations

from dataclasses import dataclass, field

from country_swing_fsm.enums import Direction, MoveType, PositionType, Role


@dataclass(slots=True, frozen=True)
class SubPosition:
    role: Role
    start_step_foot: Direction
    hands_joined: list[Direction]


@dataclass(slots=True)
class Position:
    position_id: str = ""
    label: str | None = None
    crossed: bool | None = None
    position_type: PositionType = PositionType.OPEN
    outgoing_moves: list[OutgoingMove] = field(default_factory=list)
    sub_positions: list[SubPosition] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.sub_positions) != 2:
            raise ValueError("A position must contain exactly two sub-positions.")

        roles = {sub_position.role for sub_position in self.sub_positions}
        if roles != {Role.LEAD, Role.FOLLOW}:
            raise ValueError("A position must contain one lead and one follow sub-position.")

        hand_counts = {len(sub_position.hands_joined) for sub_position in self.sub_positions}
        if len(hand_counts) != 1:
            raise ValueError(
                "Lead and follow sub-positions must have the same number of joined hands."
            )

    def sub_position_for_role(self, role: Role) -> SubPosition:
        for sub_position in self.sub_positions:
            if sub_position.role == role:
                return sub_position
        raise ValueError(f"Missing sub-position for role {role.value}.")

    @property
    def lead_start_step_foot(self) -> Direction:
        return self.sub_position_for_role(Role.LEAD).start_step_foot
    
    @property
    def follow_start_step_foot(self) -> Direction:
        return self.sub_position_for_role(Role.FOLLOW).start_step_foot


@dataclass(slots=True)
class SubMove:
    role: Role
    is_turn: bool
    _source_position: Position | None = field(default=None, init=False, repr=False)

    @property
    def turn_direction(self) -> Direction | None:
        if not self.is_turn or self._source_position is None:
            return None
        return self._source_position.sub_position_for_role(self.role).start_step_foot


@dataclass(slots=True)
class Move:
    label: str | None
    source: Position
    destination: Position
    move_type: MoveType
    sub_moves: list[SubMove] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.sub_moves) != 2:
            raise ValueError("A move must contain exactly two sub-moves.")

        roles = {sub_move.role for sub_move in self.sub_moves}
        if roles != {Role.LEAD, Role.FOLLOW}:
            raise ValueError("A move must contain one lead and one follow sub-move.")

        for sub_move in self.sub_moves:
            sub_move._source_position = self.source

    def sub_move_for_role(self, role: Role) -> SubMove:
        for sub_move in self.sub_moves:
            if sub_move.role == role:
                return sub_move
        raise ValueError(f"Missing sub-move for role {role.value}.")


@dataclass(slots=True)
class OutgoingMove:
    outgoing_move: Move
    destination_position: Position
