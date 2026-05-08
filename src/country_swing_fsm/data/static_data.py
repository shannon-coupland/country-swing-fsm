from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from country_swing_fsm.enums import Direction, MoveType, PositionType, Role
from country_swing_fsm.models import Move, SubMove, OutgoingMove, Position, SubPosition


DestinationReference = Position | Callable[[], Position] | str


@dataclass(frozen=True, slots=True)
class MoveDefinition:
    label: str | None
    move_type: MoveType
    is_lead_turn: bool
    is_follow_turn: bool
    destination_reference: DestinationReference


@dataclass(slots=True)
class PositionDefinition:
    position: Position
    move_definitions: list[MoveDefinition]


_POSITION_DEFINITIONS: list[PositionDefinition] = []
_GROUP_ORDER = {
    (False, 1): 0,
    (False, 2): 1,
    (True, 1): 2,
    (True, 2): 3,
}
_POSITION_TYPE_ORDER = {
    PositionType.OPEN: 0,
    PositionType.TWISTED: 1,
    PositionType.ACCENT: 2,
}
_DIRECTION_ORDER = {
    Direction.LEFT: 0,
    Direction.RIGHT: 1,
}


def create_move(
    label: str | None,
    move_type: MoveType,
    is_lead_turn: bool,
    is_follow_turn: bool,
    dest_position: DestinationReference,
) -> MoveDefinition:
    return MoveDefinition(
        label=label,
        move_type=move_type,
        is_lead_turn=is_lead_turn,
        is_follow_turn=is_follow_turn,
        destination_reference=dest_position,
    )


def create_position(
    *,
    lead_start_step_foot: Direction,
    follow_start_step_foot: Direction,
    lead_hands_joined: list[Direction],
    follow_hands_joined: list[Direction],
    position_type: PositionType,
    moves: list[MoveDefinition],
    label: str | None = None,
    crossed: bool | None = None,
) -> Position:
    hand_count = len(lead_hands_joined)
    if hand_count != len(follow_hands_joined):
        raise ValueError("Lead and follow must have the same number of joined hands.")

    if hand_count == 1:
        if crossed is not None:
            raise ValueError(
                "crossed must not be supplied for single-hand positions; it is derived."
            )
        crossed = lead_hands_joined[0] == follow_hands_joined[0]
    elif hand_count == 0:
        if crossed is not None:
            raise ValueError(
                "crossed must not be supplied for no-hand positions; it is undefined."
            )
        crossed = None
    elif crossed is None:
        raise ValueError("crossed must be supplied for positions with other than one hand.")

    position = Position(
        label=label,
        crossed=crossed,
        position_type=position_type,
        sub_positions=[
            SubPosition(
                role=Role.LEAD,
                start_step_foot=lead_start_step_foot,
                hands_joined=lead_hands_joined,
            ),
            SubPosition(
                role=Role.FOLLOW,
                start_step_foot=follow_start_step_foot,
                hands_joined=follow_hands_joined,
            ),
        ],
    )
    _POSITION_DEFINITIONS.append(
        PositionDefinition(position=position, move_definitions=moves or [])
    )
    return position


def _resolve_destination(destination_reference: DestinationReference) -> Position:
    if isinstance(destination_reference, str):
        destination = globals()[destination_reference]
        if not isinstance(destination, Position):
            raise TypeError(
                f"Destination reference '{destination_reference}' did not resolve to a Position."
            )
        return destination
    if callable(destination_reference):
        return destination_reference()
    return destination_reference


def _build_all_moves() -> list[Move]:
    all_moves: list[Move] = []

    for position_definition in _POSITION_DEFINITIONS:
        position_definition.position.outgoing_moves = []

        for move_definition in position_definition.move_definitions:
            destination = _resolve_destination(move_definition.destination_reference)
            move = Move(
                label=move_definition.label,
                source=position_definition.position,
                destination=destination,
                move_type=move_definition.move_type,
                sub_moves=[
                    SubMove(role=Role.LEAD, is_turn=move_definition.is_lead_turn),
                    SubMove(role=Role.FOLLOW, is_turn=move_definition.is_follow_turn),
                ],
            )
            all_moves.append(move)
            position_definition.position.outgoing_moves.append(
                OutgoingMove(
                    outgoing_move=move,
                    destination_position=destination,
                )
            )

    return all_moves


def _assign_position_ids() -> None:
    ordered_positions = [
        *_sorted_column_positions(
            [
                position
                for position in ALL_POSITIONS
                if (
                    position.position_type != PositionType.ACCENT
                    and position.lead_start_step_foot == Direction.LEFT
                )
            ]
        ),
        *_sorted_column_positions(
            [
                position
                for position in ALL_POSITIONS
                if (
                    position.position_type != PositionType.ACCENT
                    and position.lead_start_step_foot == Direction.RIGHT
                )
            ]
        ),
        *_sorted_impact_positions(
            [position for position in ALL_POSITIONS if position.position_type == PositionType.ACCENT]
        ),
    ]

    for index, position in enumerate(ordered_positions, start=1):
        position.position_id = str(index)


def _sorted_column_positions(positions: list[Position]) -> list[Position]:
    return sorted(positions, key=_column_position_sort_key)


def _sorted_impact_positions(positions: list[Position]) -> list[Position]:
    return sorted(
        positions,
        key=lambda position: (
            _POSITION_TYPE_ORDER[position.position_type],
            _DIRECTION_ORDER[position.lead_start_step_foot],
            _hands_joined_sort_key(position),
            position.label or "",
        ),
    )


def _column_position_sort_key(position: Position) -> tuple[int, int, int, tuple[int, ...], str]:
    return (
        _GROUP_ORDER.get(
            (position.crossed, len(position.sub_position_for_role(Role.LEAD).hands_joined)),
            len(_GROUP_ORDER),
        ),
        _POSITION_TYPE_ORDER[position.position_type],
        _single_hand_priority(position),
        _hands_joined_sort_key(position),
        position.label or "",
    )


def _single_hand_priority(position: Position) -> int:
    follow_hands_joined = position.sub_position_for_role(Role.FOLLOW).hands_joined
    if len(follow_hands_joined) != 1:
        return 0
    return 0 if follow_hands_joined[0] == Direction.RIGHT else 1


def _hands_joined_sort_key(position: Position) -> tuple[int, ...]:
    return tuple(
        _DIRECTION_ORDER[direction]
        for direction in position.sub_position_for_role(Role.LEAD).hands_joined
    )


# TODO Add all Moves that point back to own state

# First Half Basic Positions------------------------------------------------------------------------------------------------------------------

FIRST_HALF = create_position(
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.LEFT],
    follow_hands_joined=[Direction.RIGHT],
    position_type=PositionType.OPEN,
    moves=[
        create_move(
            label="Behind the Back Pass",
            move_type=MoveType.BASIC,
            is_lead_turn=True,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Arch",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=True,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Pancake Outside Turn(s)",
            move_type=MoveType.BASIC,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Push Off Outside Turn",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Offer Hand + Drop",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_OPPOSITE,
        ),
        create_move(
            label="Offer Hand + Hold",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_BOTH,
        ),
        create_move(
            label="Rainbow Outside Turn(s)",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_CROSSED,
        ),
        create_move(
            label="Behind the Back Pass - Switch Hands",
            move_type=MoveType.BASIC,
            is_lead_turn=True,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_CROSSED,
        )
    ],
)

FIRST_HALF_OPPOSITE = create_position(
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.RIGHT],
    follow_hands_joined=[Direction.LEFT],
    position_type=PositionType.OPEN,
    moves=[
        create_move(
            label="Offer Hand + Drop",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="Offer Hand + Hold",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn = False,
            is_follow_turn = False,
            dest_position=lambda: FIRST_HALF_BOTH
        ),
        create_move(
            label="Inside Turn(s)",
            move_type=MoveType.BASIC,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_OPPOSITE,
        )
    ],
)

FIRST_HALF_CATCH = create_position(
    label="Catch Right Side",
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.LEFT],
    follow_hands_joined=[Direction.RIGHT],
    position_type=PositionType.TWISTED,
    moves=[
        create_move(
            label="Pull Into Reset",
            move_type=MoveType.BASIC,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Fishtail",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_CATCH,
        ),
        create_move(
            label="Pull Into Duck Turn",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=-True,
            dest_position=lambda: SECOND_HALF_OPPOSITE
        )
    ],
)

FIRST_HALF_BOTH = create_position(
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.LEFT, Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT, Direction.LEFT],
    crossed=False,
    position_type=PositionType.OPEN,
    moves=[
        create_move(
            label="Behind the Back Pass (Infinity)",
            move_type=MoveType.BASIC,
            is_lead_turn=True,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_BOTH,
        ),
        create_move(
            label="Spinneroo (Step to Left)",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_BOTH_TWISTED,
        ),
        create_move(
            label="Outside Turn (Hammerlock)",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_BOTH_HAMMERLOCK,
        ),
        create_move(
            label="Arm Slide",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_CROSSED,
        ),
        create_move(
            label="Opposite Hand Arm Slide",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_CROSSED_OPPOSITE,
        ),
        create_move(
            label="Drop Right Hand",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF
        ),
        create_move(
            label="Drop Left Hand",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_OPPOSITE
        ),
        create_move(
            label="Basic Check Left",
            move_type=MoveType.BASIC,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_BOTH
        ),
        create_move(
            label="Pretzel First Half (lead under left, turn follow with left)",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=True,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_BOTH_BACK_TO_BACK
        ),
        create_move(
            label="Full Pretzel",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=True,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_BOTH
        )
    ],
)

FIRST_HALF_BOTH_CUDDLE = create_position(
    label="Cuddle",
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.LEFT, Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT, Direction.LEFT],
    crossed=False,
    position_type=PositionType.TWISTED,
    moves=[
        create_move(
            label="Trust Fall",
            move_type=MoveType.ACCENT,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_TRUST_FALL,
        ),
        create_move(
            label="Stretch",
            move_type=MoveType.BASIC,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_OPPOSITE,
        ),
        create_move(
            label="Unwind",
            move_type=MoveType.BASIC,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_BOTH,
        ),
        create_move(
            label="Cuddle Lean",
            move_type=MoveType.ACCENT,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_BOTH_CUDDLE
        ),
        create_move(
            label="Rotate",
            move_type=MoveType.ROTATE,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_BOTH_CUDDLE
        )
    ],
)

FIRST_HALF_BOTH_BACK_TO_BACK = create_position(
    label="Back to Back Left",
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.LEFT, Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT, Direction.LEFT],
    position_type=PositionType.TWISTED,
    crossed=False,
    moves=[
        create_move(
            label="Pretzel Second Half (follow under right, lead turns under left)",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=True,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_BOTH
        )
    ]
)

FIRST_HALF_CROSSED = create_position(
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT],
    position_type=PositionType.OPEN,
    moves=[
        create_move(
            label="Behind the Back Pass",
            move_type=MoveType.BASIC,
            is_lead_turn=True,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Behind the Back Pass - Keep Hands Switched",
            move_type=MoveType.BASIC,
            is_lead_turn=True,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_CROSSED,
        ),
        create_move(
            label="Reverse Sweetheart Left",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=True,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_CROSSED_REVERSE_SWEETHEART_LEFT
        ),
        create_move(
            label="Offer Hand + Drop",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_CROSSED_OPPOSITE,
        )
    ],
)

FIRST_HALF_CROSSED_OPPOSITE = create_position(
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.LEFT],
    follow_hands_joined=[Direction.LEFT],
    position_type=PositionType.OPEN,
    moves=[
        create_move(
            label="Hairbrush",
            move_type=MoveType.CROSSED_ESCAPE,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Offer Hand + Drop",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_CROSSED,
        ),
        create_move(
            label="Offer Hand + Hold",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_CROSSED_BOTH,
        ),
        create_move(
            label="Inside Turn(s)",
            move_type=MoveType.BASIC,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_CROSSED_OPPOSITE,
        ),
        create_move(
            label="Shoulder Lean",
            move_type=MoveType.ACCENT,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_SHOULDER_LEAN_LEFT
        )
    ],
)

FIRST_HALF_CROSSED_BOTH = create_position(
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.LEFT, Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT, Direction.LEFT],
    crossed=True,
    position_type=PositionType.OPEN,
    moves=[
        create_move(
            label="Hairbrush",
            move_type=MoveType.CROSSED_ESCAPE,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_BOTH,
        ),
        create_move(
            label="Sunrise",
            move_type=MoveType.CROSSED_ESCAPE,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_BOTH,
        ),
        create_move(
            label="Spinneroo (Step to Left)",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_CROSSED_BOTH,
        ),
        create_move(
            label="Duck Under Spinneroo (Turn to Left)",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=True,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_CROSSED_BOTH,
        ),
        create_move(
            label="Drop Left Hand",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_CROSSED
        ),
        create_move(
            label="Drop Right Hand",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_CROSSED_OPPOSITE
        )
    ],
)

FIRST_HALF_CROSSED_REVERSE_SWEETHEART_LEFT = create_position(
    label="Reverse Sweetheart Left",
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.LEFT, Direction.RIGHT],
    follow_hands_joined=[Direction.LEFT, Direction.RIGHT],
    position_type=PositionType.TWISTED,
    crossed=True,
    moves=[
        create_move(
            label="Rotate",
            move_type=MoveType.ROTATE,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_CROSSED_REVERSE_SWEETHEART_LEFT
        ),
        create_move(
            label="Drop Right Hand and Lasso",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda:SECOND_HALF_CROSSED_OPPOSITE
        ),
        create_move(
            label="Drop Right Hand + Lasso Into Shoulder Lean Left",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_SHOULDER_LEAN_LEFT
        ),
        create_move(
            label="Pull to Right",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_CROSSED_REVERSE_SWEETHEART_RIGHT
        )
    ]
)


# Second Half Basic Positions------------------------------------------------------------------------------------------------------------------

SECOND_HALF = create_position(
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.LEFT],
    follow_hands_joined=[Direction.RIGHT],
    position_type=PositionType.OPEN,
    moves=[
        create_move(
            label="Inside Turn(s)",
            move_type=MoveType.BASIC,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="Inside Turn(s) Into Dip",
            move_type=MoveType.ACCENT,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_DIP,
        ),
        create_move(
            label="Right Shoulder Duck",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="Stop at Left Shoulder",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_CATCH,
        ),
        create_move(
            label="Offer Right Hand + Drop",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_OPPOSITE,
        ),
        create_move(
            label="Offer Hand + Hold",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_BOTH
        ),
        create_move(
            label="Inside Turn(s) - Join Hands",
            move_type=MoveType.BASIC,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_BOTH,
        )
    ],
)

SECOND_HALF_OPPOSITE = create_position(
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.RIGHT],
    follow_hands_joined=[Direction.LEFT],
    position_type=PositionType.OPEN,
    moves=[
        create_move(
            label="Offer Hand + Drop",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Offer Hand + Hold",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_BOTH,
        ),
        create_move(
            label="J Hook Reset",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="J Hook Into Dip",
            move_type=MoveType.ACCENT,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_DIP,
        ),
        create_move(
            label="Outside Turn(s)",
            move_type=MoveType.BASIC,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_OPPOSITE,
        ),
        create_move(
            label="J Hook Into Cuddle",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_BOTH_CUDDLE
        ),
        create_move(
            label="Lead Hair Flip",
            move_type=MoveType.ACCENT,
            is_lead_turn=True,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_OPPOSITE
        )
    ],
)


SECOND_HALF_CATCH = create_position(
    label="Catch Left Side",
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.LEFT],
    follow_hands_joined=[Direction.RIGHT],
    position_type=PositionType.TWISTED,
    moves=[
        create_move(
            label="Fishtail",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_CATCH
        ),
        create_move(
            label="Pull Into Reset",
            move_type=MoveType.BASIC,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF
        )
    ]
)

SECOND_HALF_BOTH = create_position(
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.LEFT, Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT, Direction.LEFT],
    crossed=False,
    position_type=PositionType.OPEN,
    moves=[
        create_move(
            label="Inside Turn(s) (Infinity)",
            move_type=MoveType.BASIC,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_BOTH,
        ),
        create_move(
            label="Inside Turn Into Cuddle",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_BOTH_CUDDLE,
        ),
        create_move(
            label="Arm Slide",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_CROSSED,
        ),
        create_move(
            label="Opposite Hand Arm Slide",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_CROSSED_OPPOSITE,
        ),
        create_move(
            label="Drop Right Hand",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF
        ),
        create_move(
            label="Drop Left Hand",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_OPPOSITE
        ),
        create_move(
            label="Basic Check Right",
            move_type=MoveType.BASIC,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_BOTH
        ),
        create_move(
            label="Pretzel First Half (lead under right, turn follow with right)",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=True,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_BOTH_BACK_TO_BACK
        ),
        create_move(
            label="Full Pretzel",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=True,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_BOTH
        )
    ],
)

SECOND_HALF_BOTH_TWISTED = create_position(
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.LEFT, Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT, Direction.LEFT],
    crossed=False,
    position_type=PositionType.TWISTED,
    moves=[
        create_move(
            label="Hairbrush",
            move_type=MoveType.CROSSED_ESCAPE,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_BOTH,
        ),
        create_move(
            label="Spinneroo (Step to Right)",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_BOTH,
        )
    ],
)

SECOND_HALF_BOTH_HAMMERLOCK = create_position(
    label="Hammer Lock",
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.LEFT, Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT, Direction.LEFT],
    crossed=False,
    position_type=PositionType.TWISTED,
    moves=[
        create_move(
            label="Hair Flip",
            move_type=MoveType.ACCENT,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_OPPOSITE,
        ),
        create_move(
            label="Unwind",
            move_type=MoveType.BASIC,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_BOTH
        ),
        create_move(
            label="Duck Under Rotate",
            move_type=MoveType.ROTATE,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_BOTH_HAMMERLOCK
        ),
        create_move(
            label="Duck Under Peek",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_BOTH_HAMMERLOCK
        )
    ],
)

SECOND_HALF_BOTH_BACK_TO_BACK = create_position(
    label="Back to Back Right",
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.LEFT, Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT, Direction.LEFT],
    position_type=PositionType.TWISTED,
    crossed=False,
    moves=[
        create_move(
            label="Pretzel Second Half (follow under left, lead turns under right)",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=True,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_BOTH
        )
    ]
)

SECOND_HALF_CROSSED = create_position(
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT],
    position_type=PositionType.OPEN,
    moves=[
        create_move(
            label="Inside Turn(s) - Put Hand in Left",
            move_type=MoveType.CROSSED_ESCAPE,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="J Hook Reset",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="J Hook Into Dip",
            move_type=MoveType.ACCENT,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_DIP,
        ),
        create_move(
            label="Inside Turn(s)",
            move_type=MoveType.BASIC,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_CROSSED,
        ),
        create_move(
            label="Offer Hand + Drop",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_CROSSED_OPPOSITE,
        ),
        create_move(
            label="Offer Hand + Hold",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_CROSSED_BOTH,
        ),
        create_move(
            label="S Dip",
            move_type=MoveType.ACCENT,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_S_DIP
        ),
        create_move(
            label="Shoulder Lean",
            move_type=MoveType.ACCENT,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_SHOULDER_LEAN_RIGHT
        )
    ],
)

SECOND_HALF_CROSSED_OPPOSITE = create_position(
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.LEFT],
    follow_hands_joined=[Direction.LEFT],
    position_type=PositionType.OPEN,
    moves=[
        create_move(
            label="Hairbrush",
            move_type=MoveType.CROSSED_ESCAPE,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="Offer Right Hand + Drop",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_CROSSED,
        ),
        create_move(
            label="Inside Turn(s)",
            move_type=MoveType.BASIC,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_CROSSED_OPPOSITE,
        ),
        create_move(
            label="Reverse Sweetheart Right",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=True,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_CROSSED_REVERSE_SWEETHEART_RIGHT
        )
    ],
)

SECOND_HALF_CROSSED_BOTH = create_position(
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.LEFT, Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT, Direction.LEFT],
    crossed=True,
    position_type=PositionType.OPEN,
    moves=[
        create_move(
            label="Hairbrush",
            move_type=MoveType.CROSSED_ESCAPE,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_BOTH,
        ),
        create_move(
            label="Sunrise",
            move_type=MoveType.CROSSED_ESCAPE,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_BOTH,
        ),
        create_move(
            label="Spinneroo (Step to Right)",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_CROSSED_BOTH,
        ),create_move(
            label="Duck Under Spinneroo (Turn to Right)",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=True,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_CROSSED_BOTH,
        ),
        create_move(
            label="Drop Left Hand",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_CROSSED
        ),
        create_move(
            label="Drop Right Hand",
            move_type=MoveType.OFFER_OR_DROP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_CROSSED_OPPOSITE
        )
    ],
)

SECOND_HALF_CROSSED_REVERSE_SWEETHEART_RIGHT = create_position(
    label="Reverse Sweetheart Right",
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.LEFT, Direction.RIGHT],
    follow_hands_joined=[Direction.LEFT, Direction.RIGHT],
    position_type=PositionType.TWISTED,
    crossed=True,
    moves=[
        create_move(
            label="Rotate",
            move_type=MoveType.ROTATE,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_CROSSED_REVERSE_SWEETHEART_RIGHT
        ),
        create_move(
            label="Drop Left Hand and Lasso",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda:FIRST_HALF_CROSSED
        ),
        create_move(
            label="Lasso Into Shoulder Lean Right",
            move_type=MoveType.ACCENT,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_SHOULDER_LEAN_RIGHT
        ),
        create_move(
            label="Pull to Left",
            move_type=MoveType.SPICED_UP,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_CROSSED_REVERSE_SWEETHEART_LEFT
        )
    ]
)


# Impact / One-Off Positions
FIRST_HALF_DIP = create_position(
    label="Basic Dip",
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[],
    follow_hands_joined=[],
    position_type=PositionType.ACCENT,
    moves=[
        create_move(
            label="Dip and Reset",
            move_type=MoveType.ACCENT,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF,
        )
    ],
)

FIRST_HALF_S_DIP = create_position(
    label="S Dip",
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT],
    position_type=PositionType.ACCENT,
    moves=[
        create_move(
            label="Dip and Reset",
            move_type=MoveType.ACCENT,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_CROSSED,
        )
    ],
)

FIRST_HALF_TRUST_FALL = create_position(
    label="Trust Fall",
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[],
    follow_hands_joined=[],
    position_type=PositionType.ACCENT,
    moves=[
        create_move(
            label="Trust Fall and Reset",
            move_type=MoveType.ACCENT,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF,
        )
    ],
)

FIRST_HALF_SHOULDER_LEAN_LEFT = create_position(
    label="Shoulder Lean Left",
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.LEFT],
    follow_hands_joined=[Direction.LEFT],
    position_type=PositionType.ACCENT,
    moves=[
        create_move(
            label="Lean and Arm Slide",
            move_type=MoveType.ACCENT,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_OPPOSITE,
        ),
        create_move(
            label="Lean and Turn with Shoulder Hand",
            move_type=MoveType.ACCENT,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_CROSSED_OPPOSITE
        )
    ],
)

SECOND_HALF_SHOULDER_LEAN_RIGHT = create_position(
    label="Shoulder Lean Right",
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT],
    position_type=PositionType.ACCENT,
    moves=[
        create_move(
            label="Lean and Arm Slide",
            move_type=MoveType.ACCENT,
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="Lean and Turn with Shoulder Hand",
            move_type=MoveType.ACCENT,
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_CROSSED
        )
    ],
)


ALL_POSITIONS: list[Position] = [definition.position for definition in _POSITION_DEFINITIONS]
ALL_MOVES = _build_all_moves()
_assign_position_ids()
