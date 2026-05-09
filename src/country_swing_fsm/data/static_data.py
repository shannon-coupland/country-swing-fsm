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
    lead_turn_direction: Direction | None
    follow_turn_direction: Direction | None
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
_DIRECTION_ORDER = {
    Direction.LEFT: 0,
    Direction.RIGHT: 1,
}


def create_move(
    label: str | None,
    move_type: MoveType,
    lead_turn_direction: Direction | None,
    follow_turn_direction: Direction | None,
    dest_position: DestinationReference,
) -> MoveDefinition:
    return MoveDefinition(
        label=label,
        move_type=move_type,
        lead_turn_direction=lead_turn_direction,
        follow_turn_direction=follow_turn_direction,
        destination_reference=dest_position,
    )


def create_position(
    *,
    position_id: int,
    lead_start_step_foot: Direction,
    follow_start_step_foot: Direction,
    lead_hands_joined: list[Direction],
    follow_hands_joined: list[Direction],
    position_type: PositionType,
    moves: list[MoveDefinition],
    label: str | None = None,
    crossed: bool | None = None,
) -> Position:
    if not isinstance(position_id, int):
        raise TypeError("position_id must be an int.")

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
        position_id=position_id,
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
    _validate_position_ids()
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
                    SubMove(
                        role=Role.LEAD,
                        turn_direction=move_definition.lead_turn_direction,
                    ),
                    SubMove(
                        role=Role.FOLLOW,
                        turn_direction=move_definition.follow_turn_direction,
                    ),
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


def _validate_position_ids() -> None:
    position_ids = [position.position_id for position in ALL_POSITIONS]
    if len(set(position_ids)) != len(position_ids):
        raise ValueError("Position IDs must be unique.")

    left_positions = _sorted_column_positions(
        [
            position
            for position in ALL_POSITIONS
            if (
                position.position_type != PositionType.ACCENT
                and position.lead_start_step_foot == Direction.LEFT
            )
        ]
    )
    right_positions = _sorted_column_positions(
        [
            position
            for position in ALL_POSITIONS
            if (
                position.position_type != PositionType.ACCENT
                and position.lead_start_step_foot == Direction.RIGHT
            )
        ]
    )
    accent_positions = _sorted_accent_positions(
        [position for position in ALL_POSITIONS if position.position_type == PositionType.ACCENT]
    )

    _validate_side_position_ids("left", left_positions)
    _validate_side_position_ids("right", right_positions)

    if left_positions and right_positions and max(position.position_id for position in left_positions) >= min(
        position.position_id for position in right_positions
    ):
        raise ValueError("All left-side position IDs must be less than all right-side position IDs.")

    if right_positions and accent_positions and max(position.position_id for position in right_positions) >= min(
        position.position_id for position in accent_positions
    ):
        raise ValueError("All right-side position IDs must be less than all accent position IDs.")


def _validate_side_position_ids(side_label: str, positions: list[Position]) -> None:
    sorted_by_id = sorted(positions, key=lambda position: position.position_id)
    previous_group_index = -1
    previous_position_id = None
    for position in sorted_by_id:
        if previous_position_id is not None and position.position_id <= previous_position_id:
            raise ValueError(f"{side_label.title()}-side position IDs must be strictly increasing.")
        previous_position_id = position.position_id

        group_index = _GROUP_ORDER.get(
            (position.crossed, len(position.sub_position_for_role(Role.LEAD).hands_joined)),
            len(_GROUP_ORDER),
        )
        if group_index < previous_group_index:
            raise ValueError(
                f"{side_label.title()}-side position IDs must preserve the group ordering: "
                "uncrossed single hand, uncrossed two hand, crossed single hand, crossed both hand."
            )
        previous_group_index = group_index


def _sorted_column_positions(positions: list[Position]) -> list[Position]:
    return sorted(positions, key=lambda position: position.position_id)


def _sorted_accent_positions(positions: list[Position]) -> list[Position]:
    return sorted(positions, key=lambda position: position.position_id)


def _hands_joined_sort_key(position: Position) -> tuple[int, ...]:
    return tuple(
        _DIRECTION_ORDER[direction]
        for direction in position.sub_position_for_role(Role.LEAD).hands_joined
    )

# First Half Basic Positions------------------------------------------------------------------------------------------------------------------

FIRST_HALF = create_position(
    position_id=1,
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.LEFT],
    follow_hands_joined=[Direction.RIGHT],
    position_type=PositionType.OPEN,
    moves=[
        create_move(
            label="Behind the Back Pass",
            move_type=MoveType.BASIC,
            lead_turn_direction=Direction.LEFT,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Arch",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=Direction.LEFT,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Pancake Outside Turn(s)",
            move_type=MoveType.BASIC,
            lead_turn_direction=None,
            follow_turn_direction=Direction.RIGHT,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Push Off Outside Turn",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=Direction.RIGHT,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Offer Hand + Drop",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_OPPOSITE,
        ),
        create_move(
            label="Offer Hand + Hold",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_BOTH,
        ),
        create_move(
            label="Rainbow Outside Turn(s)",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=Direction.RIGHT,
            dest_position=lambda: SECOND_HALF_CROSSED,
        ),
        create_move(
            label="Behind the Back Pass - Switch Hands",
            move_type=MoveType.BASIC,
            lead_turn_direction=Direction.LEFT,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_CROSSED,
        )
    ],
)

FIRST_HALF_OPPOSITE = create_position(
    position_id=2,
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.RIGHT],
    follow_hands_joined=[Direction.LEFT],
    position_type=PositionType.OPEN,
    moves=[
        create_move(
            label="Offer Hand + Drop",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="Offer Hand + Hold",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_BOTH
        ),
        create_move(
            label="Inside Turn(s)",
            move_type=MoveType.BASIC,
            lead_turn_direction=None,
            follow_turn_direction=Direction.RIGHT,
            dest_position=lambda: SECOND_HALF_OPPOSITE,
        )
    ],
)

FIRST_HALF_CATCH = create_position(
    position_id=3,
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
            lead_turn_direction=None,
            follow_turn_direction=Direction.RIGHT,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Fishtail",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=Direction.RIGHT,
            dest_position=lambda: SECOND_HALF_CATCH,
        ),
        create_move(
            label="Pull Into Duck Turn",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=Direction.RIGHT,
            dest_position=lambda: SECOND_HALF_OPPOSITE
        )
    ],
)

FIRST_HALF_BOTH = create_position(
    position_id=4,
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
            lead_turn_direction=Direction.LEFT,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_BOTH,
        ),
        create_move(
            label="Spinneroo (Step to Left)",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=Direction.RIGHT,
            dest_position=lambda: SECOND_HALF_BOTH_TWISTED,
        ),
        create_move(
            label="Outside Turn (Hammerlock)",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=Direction.RIGHT,
            dest_position=lambda: SECOND_HALF_BOTH_HAMMERLOCK,
        ),
        create_move(
            label="Arm Slide",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_CROSSED,
        ),
        create_move(
            label="Opposite Hand Arm Slide",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_CROSSED_OPPOSITE,
        ),
        create_move(
            label="Drop Right Hand",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF
        ),
        create_move(
            label="Drop Left Hand",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_OPPOSITE
        ),
        create_move(
            label="Basic Check Left",
            move_type=MoveType.BASIC,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_BOTH
        ),
        create_move(
            label="Pretzel First Half (lead under left, turn follow with left)",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=Direction.LEFT,
            follow_turn_direction=Direction.RIGHT,
            dest_position=lambda: FIRST_HALF_BOTH_BACK_TO_BACK
        ),
        create_move(
            label="Full Pretzel",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=Direction.LEFT,
            follow_turn_direction=Direction.RIGHT,
            dest_position=lambda: FIRST_HALF_BOTH
        )
    ],
)

FIRST_HALF_BOTH_CUDDLE = create_position(
    position_id=5,
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
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_TRUST_FALL,
        ),
        create_move(
            label="Stretch",
            move_type=MoveType.BASIC,
            lead_turn_direction=None,
            follow_turn_direction=Direction.RIGHT,
            dest_position=lambda: SECOND_HALF_OPPOSITE,
        ),
        create_move(
            label="Unwind",
            move_type=MoveType.BASIC,
            lead_turn_direction=None,
            follow_turn_direction=Direction.RIGHT,
            dest_position=lambda: SECOND_HALF_BOTH,
        ),
        create_move(
            label="Cuddle Lean",
            move_type=MoveType.ACCENT,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_BOTH_CUDDLE
        ),
        create_move(
            label="Rotate",
            move_type=MoveType.ROTATE,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_BOTH_CUDDLE
        ),
        create_move(
            label="Double Turn Into Hammerlock",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=Direction.RIGHT,
            dest_position=lambda: SECOND_HALF_BOTH_HAMMERLOCK
        )
    ],
)

FIRST_HALF_BOTH_BACK_TO_BACK = create_position(
    position_id=6,
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
            lead_turn_direction=Direction.LEFT,
            follow_turn_direction=Direction.RIGHT,
            dest_position=lambda: FIRST_HALF_BOTH
        ),
        create_move(
            label="Rotate Right",
            move_type=MoveType.ROTATE,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_BOTH_BACK_TO_BACK
        ),
        create_move(
            label="Pull Left and Peek",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_BOTH_BACK_TO_BACK
        ),
    ]
)

FIRST_HALF_CROSSED = create_position(
    position_id=7,
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT],
    position_type=PositionType.OPEN,
    moves=[
        create_move(
            label="Behind the Back Pass - Reset Hands",
            move_type=MoveType.BASIC,
            lead_turn_direction=Direction.LEFT,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Behind the Back Pass - Keep Hands Switched",
            move_type=MoveType.BASIC,
            lead_turn_direction=Direction.LEFT,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_CROSSED,
        ),
        create_move(
            label="Reverse Sweetheart Left",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=Direction.LEFT,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_CROSSED_REVERSE_SWEETHEART_LEFT
        ),
        create_move(
            label="Offer Hand + Drop",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_CROSSED_OPPOSITE,
        )
    ],
)

FIRST_HALF_CROSSED_OPPOSITE = create_position(
    position_id=8,
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.LEFT],
    follow_hands_joined=[Direction.LEFT],
    position_type=PositionType.OPEN,
    moves=[
        create_move(
            label="Hairbrush",
            move_type=MoveType.CROSSED_ESCAPE,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Offer Hand + Drop",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_CROSSED,
        ),
        create_move(
            label="Offer Hand + Hold",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_CROSSED_BOTH,
        ),
        create_move(
            label="Inside Turn(s)",
            move_type=MoveType.BASIC,
            lead_turn_direction=None,
            follow_turn_direction=Direction.RIGHT,
            dest_position=lambda: SECOND_HALF_CROSSED_OPPOSITE,
        ),
        create_move(
            label="Shoulder Lean",
            move_type=MoveType.ACCENT,
            lead_turn_direction=None,
            follow_turn_direction=Direction.RIGHT,
            dest_position=lambda: FIRST_HALF_SHOULDER_LEAN_LEFT
        )
    ],
)

FIRST_HALF_CROSSED_BOTH = create_position(
    position_id=9,
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
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_BOTH,
        ),
        create_move(
            label="Sunrise",
            move_type=MoveType.CROSSED_ESCAPE,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_BOTH,
        ),
        create_move(
            label="Spinneroo (Step to Left)",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=Direction.RIGHT,
            dest_position=lambda: SECOND_HALF_CROSSED_BOTH,
        ),
        create_move(
            label="Duck Under Spinneroo (Turn to Left)",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=Direction.LEFT,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_CROSSED_BOTH,
        ),
        create_move(
            label="Drop Left Hand",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_CROSSED
        ),
        create_move(
            label="Drop Right Hand",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_CROSSED_OPPOSITE
        )
    ],
)

FIRST_HALF_CROSSED_REVERSE_SWEETHEART_LEFT = create_position(
    position_id=10,
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
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_CROSSED_REVERSE_SWEETHEART_LEFT
        ),
        create_move(
            label="Drop Right Hand and Lasso",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=Direction.RIGHT,
            dest_position=lambda:SECOND_HALF_CROSSED_OPPOSITE
        ),
        create_move(
            label="Drop Right Hand + Lasso Into Shoulder Lean Left",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=Direction.RIGHT,
            dest_position=lambda: FIRST_HALF_SHOULDER_LEAN_LEFT
        ),
        create_move(
            label="Pull to Right",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_CROSSED_REVERSE_SWEETHEART_RIGHT
        )
    ]
)


# Second Half Basic Positions------------------------------------------------------------------------------------------------------------------

SECOND_HALF = create_position(
    position_id=11,
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.LEFT],
    follow_hands_joined=[Direction.RIGHT],
    position_type=PositionType.OPEN,
    moves=[
        create_move(
            label="Inside Turn(s)",
            move_type=MoveType.BASIC,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="Inside Turn(s) Into Dip",
            move_type=MoveType.ACCENT,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF_DIP,
        ),
        create_move(
            label="Right Shoulder Duck",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="Stop at Left Shoulder",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF_CATCH,
        ),
        create_move(
            label="Offer Right Hand + Drop",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_OPPOSITE,
        ),
        create_move(
            label="Offer Hand + Hold",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_BOTH
        ),
        create_move(
            label="Inside Turn(s) - Join Hands",
            move_type=MoveType.BASIC,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF_BOTH,
        )
    ],
)

SECOND_HALF_OPPOSITE = create_position(
    position_id=12,
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.RIGHT],
    follow_hands_joined=[Direction.LEFT],
    position_type=PositionType.OPEN,
    moves=[
        create_move(
            label="Offer Hand + Drop",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Offer Hand + Hold",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_BOTH,
        ),
        create_move(
            label="J Hook Reset",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="J Hook Into Dip",
            move_type=MoveType.ACCENT,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF_DIP,
        ),
        create_move(
            label="Outside Turn(s)",
            move_type=MoveType.BASIC,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF_OPPOSITE,
        ),
        create_move(
            label="J Hook Into Cuddle",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF_BOTH_CUDDLE
        ),
        create_move(
            label="Lead Hair Flip",
            move_type=MoveType.ACCENT,
            lead_turn_direction=Direction.RIGHT,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_OPPOSITE
        )
    ],
)


SECOND_HALF_CATCH = create_position(
    position_id=13,
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
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF_CATCH
        ),
        create_move(
            label="Pull Into Reset",
            move_type=MoveType.BASIC,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF
        )
    ]
)

SECOND_HALF_BOTH = create_position(
    position_id=14,
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
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF_BOTH,
        ),
        create_move(
            label="Inside Turn Into Cuddle",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF_BOTH_CUDDLE,
        ),
        create_move(
            label="Arm Slide",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_CROSSED,
        ),
        create_move(
            label="Opposite Hand Arm Slide",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_CROSSED_OPPOSITE,
        ),
        create_move(
            label="Drop Right Hand",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF
        ),
        create_move(
            label="Drop Left Hand",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_OPPOSITE
        ),
        create_move(
            label="Basic Check Right",
            move_type=MoveType.BASIC,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_BOTH
        ),
        create_move(
            label="Pretzel First Half (lead under right, turn follow with right)",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=Direction.RIGHT,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: SECOND_HALF_BOTH_BACK_TO_BACK
        ),
        create_move(
            label="Full Pretzel",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=Direction.RIGHT,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: SECOND_HALF_BOTH
        )
    ],
)

SECOND_HALF_BOTH_HAMMERLOCK = create_position(
    position_id=15,
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
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_OPPOSITE,
        ),
        create_move(
            label="Unwind",
            move_type=MoveType.BASIC,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF_BOTH
        ),
        create_move(
            label="Duck Under",
            move_type=MoveType.ROTATE,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_BOTH_BACK_TO_BACK
        ),
        create_move(
            label="Double Turn Into Cuddle",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF_BOTH_CUDDLE
        )
    ],
)

SECOND_HALF_BOTH_BACK_TO_BACK = create_position(
    position_id=16,
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
            lead_turn_direction=Direction.RIGHT,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: SECOND_HALF_BOTH
        ),
        create_move(
            label="Rotate Left",
            move_type=MoveType.ROTATE,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_BOTH_BACK_TO_BACK
        ),
        create_move(
            label="Pull Right and Peek",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_BOTH_BACK_TO_BACK
        ),
    ]
)

SECOND_HALF_BOTH_TWISTED = create_position(
    position_id=17,
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
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_BOTH,
        ),
        create_move(
            label="Spinneroo (Step to Right)",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF_BOTH,
        )
    ],
)

SECOND_HALF_CROSSED = create_position(
    position_id=18,
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT],
    position_type=PositionType.OPEN,
    moves=[
        create_move(
            label="Inside Turn(s) - Put Hand in Left",
            move_type=MoveType.CROSSED_ESCAPE,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="J Hook Reset",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="J Hook Into Dip",
            move_type=MoveType.ACCENT,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF_DIP,
        ),
        create_move(
            label="Inside Turn(s)",
            move_type=MoveType.BASIC,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF_CROSSED,
        ),
        create_move(
            label="Offer Hand + Drop",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_CROSSED_OPPOSITE,
        ),
        create_move(
            label="Offer Hand + Hold",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_CROSSED_BOTH,
        ),
        create_move(
            label="S Dip",
            move_type=MoveType.ACCENT,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF_S_DIP
        ),
        create_move(
            label="Shoulder Lean",
            move_type=MoveType.ACCENT,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: SECOND_HALF_SHOULDER_LEAN_RIGHT
        ),
        create_move(
            label="Inside Turn - Join Hands",
            move_type=MoveType.BASIC,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF_CROSSED_BOTH
        )
    ],
)

SECOND_HALF_CROSSED_OPPOSITE = create_position(
    position_id=19,
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.LEFT],
    follow_hands_joined=[Direction.LEFT],
    position_type=PositionType.OPEN,
    moves=[
        create_move(
            label="Hairbrush",
            move_type=MoveType.CROSSED_ESCAPE,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="Offer Right Hand + Drop",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_CROSSED,
        ),
        create_move(
            label="Inside Turn(s)",
            move_type=MoveType.BASIC,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF_CROSSED_OPPOSITE,
        ),
        create_move(
            label="Reverse Sweetheart Right",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=Direction.RIGHT,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_CROSSED_REVERSE_SWEETHEART_RIGHT
        )
    ],
)

SECOND_HALF_CROSSED_BOTH = create_position(
    position_id=20,
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
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_BOTH,
        ),
        create_move(
            label="Sunrise",
            move_type=MoveType.CROSSED_ESCAPE,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_BOTH,
        ),
        create_move(
            label="Spinneroo (Step to Right)",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: FIRST_HALF_CROSSED_BOTH,
        ),create_move(
            label="Duck Under Spinneroo (Turn to Right)",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=Direction.RIGHT,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_CROSSED_BOTH,
        ),
        create_move(
            label="Drop Left Hand",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_CROSSED
        ),
        create_move(
            label="Drop Right Hand",
            move_type=MoveType.OFFER_OR_DROP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_CROSSED_OPPOSITE
        )
    ],
)

SECOND_HALF_CROSSED_REVERSE_SWEETHEART_RIGHT = create_position(
    position_id=21,
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
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_CROSSED_REVERSE_SWEETHEART_RIGHT
        ),
        create_move(
            label="Drop Left Hand and Lasso",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda:FIRST_HALF_CROSSED
        ),
        create_move(
            label="Lasso Into Shoulder Lean Right",
            move_type=MoveType.ACCENT,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: SECOND_HALF_SHOULDER_LEAN_RIGHT
        ),
        create_move(
            label="Pull to Left",
            move_type=MoveType.SPICED_UP,
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF_CROSSED_REVERSE_SWEETHEART_LEFT
        )
    ]
)


# Accent Positions
FIRST_HALF_DIP = create_position(
    position_id=22,
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
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF,
        )
    ],
)

FIRST_HALF_S_DIP = create_position(
    position_id=23,
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
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_CROSSED,
        )
    ],
)

FIRST_HALF_TRUST_FALL = create_position(
    position_id=24,
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
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF,
        )
    ],
)

FIRST_HALF_SHOULDER_LEAN_LEFT = create_position(
    position_id=25,
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
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: SECOND_HALF_OPPOSITE,
        ),
        create_move(
            label="Lean and Turn with Shoulder Hand",
            move_type=MoveType.ACCENT,
            lead_turn_direction=None,
            follow_turn_direction=Direction.LEFT,
            dest_position=lambda: SECOND_HALF_CROSSED_OPPOSITE
        )
    ],
)

SECOND_HALF_SHOULDER_LEAN_RIGHT = create_position(
    position_id=26,
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
            lead_turn_direction=None,
            follow_turn_direction=None,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="Lean and Turn with Shoulder Hand",
            move_type=MoveType.ACCENT,
            lead_turn_direction=None,
            follow_turn_direction=Direction.RIGHT,
            dest_position=lambda: FIRST_HALF_CROSSED
        )
    ],
)


ALL_POSITIONS: list[Position] = [definition.position for definition in _POSITION_DEFINITIONS]
ALL_MOVES = _build_all_moves()
