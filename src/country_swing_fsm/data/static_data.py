from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from country_swing_fsm.enums import Direction, Role
from country_swing_fsm.models import Move, SubMove, OutgoingMove, Position, SubPosition


DestinationReference = Position | Callable[[], Position] | str


@dataclass(frozen=True, slots=True)
class MoveDefinition:
    label: str | None
    is_lead_turn: bool
    is_follow_turn: bool
    destination_reference: DestinationReference


@dataclass(slots=True)
class PositionDefinition:
    position: Position
    move_definitions: list[MoveDefinition]


_POSITION_DEFINITIONS: list[PositionDefinition] = []


def create_move(
    label: str | None,
    is_lead_turn: bool,
    is_follow_turn: bool,
    dest_position: DestinationReference,
) -> MoveDefinition:
    return MoveDefinition(
        label=label,
        is_lead_turn=is_lead_turn,
        is_follow_turn=is_follow_turn,
        destination_reference=dest_position,
    )


def create_position(
    label: str | None,
    lead_start_step_foot: Direction,
    follow_start_step_foot: Direction,
    lead_hands_joined: list[Direction],
    follow_hands_joined: list[Direction],
    crossed: bool,
    moves: list[MoveDefinition] | None = None,
) -> Position:
    position = Position(
        label=label,
        crossed=crossed,
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


# TODO Add all Moves that point back to own state

# First Half Basic Positions------------------------------------------------------------------------------------------------------------------

FIRST_HALF = create_position(
    label="First Half Uncrossed Left Hand",
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.LEFT],
    follow_hands_joined=[Direction.RIGHT],
    crossed=False,
    moves=[
        create_move(
            label="Behind the Back Pass",
            is_lead_turn=True,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Arch",
            is_lead_turn=True,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Pancake Outside Turn(s)",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Push Off Outside Turn",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Offer Right Hand Outside Turn(s)",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_OPPOSITE,
        ),
        create_move(
            label="Rainbow Outside Turn(s)",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_CROSSED,
        ),
        create_move(
            label="Behind the Back Pass - Switch Hands",
            is_lead_turn=True,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_CROSSED,
        )
    ],
)

FIRST_HALF_OPPOSITE = create_position(
    label="First Half Uncrossed Right Hand",
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.RIGHT],
    follow_hands_joined=[Direction.LEFT],
    crossed=False,
    moves=[
        create_move(
            label="Offer Left Hand Outside Turn(s)",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Inside Turn(s)",
            is_lead_turn=True,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_OPPOSITE,
        )
    ],
)

FIRST_HALF_BOTH = create_position(
    label="First Half Uncrossed 2 Hands",
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.LEFT, Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT, Direction.LEFT],
    crossed=False,
    moves=[
        create_move(
            label="Behind the Back Pass (Infinity)",
            is_lead_turn=True,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_BOTH,
        ),
        create_move(
            label="Spinneroo (Step to Left)",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_BOTH_TWISTED,
        ),
        create_move(
            label="Outside Turn (Hammerlock)",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_BOTH_HAMMERLOCK,
        ),
        create_move(
            label="Arm Slide",
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_CROSSED,
        ),
        create_move(
            label="Opposite Hand Arm Slide",
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_CROSSED_OPPOSITE,
        )
    ],
)

FIRST_HALF_BOTH_CUDDLE = create_position(
    label="First Half Cuddle",
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.LEFT, Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT, Direction.LEFT],
    crossed=False,
    moves=[
        create_move(
            label="Trust Fall",
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_TRUST_FALL,
        ),
        create_move(
            label="Stretch",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_OPPOSITE,
        ),
        create_move(
            label="Unwind",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_BOTH,
        )
    ],
)

FIRST_HALF_CROSSED = create_position(
    label="First Half Crossed Right Hand",
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT],
    crossed=True,
    moves=[
        create_move(
            label="Behind the Back Pass",
            is_lead_turn=True,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Behind the Back Pass - Keep Hands Switched",
            is_lead_turn=True,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_CROSSED,
        ),
        create_move(
            label="Lasso Into Outside Turn",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_CROSSED_OPPOSITE,
        ),
        create_move(
            label="Lasso Into Shoulder Lean", # TODO ensure that FIRST_HALF_CROSSED_OPPOSITE can also go into SECOND_HALF_SHOULDER_LEAN
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_SHOULDER_LEAN,
        ),
        create_move(
            label="Offer Left Hand Outside Turn",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_BOTH,
        )
    ],
)

FIRST_HALF_CROSSED_OPPOSITE = create_position(
    label="First Half Crossed Left Hand",
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.LEFT],
    follow_hands_joined=[Direction.LEFT],
    crossed=True,
    moves=[
        create_move(
            label="Hairbrush",
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Offer Right Hand Outside Turn(s)",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_CROSSED,
        ),
        create_move(
            label="Inside Turn(s)",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_CROSSED_OPPOSITE,
        )
    ],
)

FIRST_HALF_CROSSED_BOTH = create_position( # TODO ensure an S Dip can happen from SECOND_HALF_CROSSED_BOTH
    label="First Half Crossed 2 Hands",
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.LEFT, Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT, Direction.LEFT],
    crossed=True,
    moves=[
        create_move(
            label="Hairbrush",
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_BOTH,
        ),
        create_move(
            label="Sunrise",
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: SECOND_HALF_BOTH,
        ),
        create_move(
            label="Spinneroo (Step to Left)",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_CROSSED_BOTH,
        )
    ],
)


# Second Half Basic Positions------------------------------------------------------------------------------------------------------------------

SECOND_HALF = create_position(
    label="Second Half Uncrossed Left Hand",
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.LEFT],
    follow_hands_joined=[Direction.RIGHT],
    crossed=False,
    moves=[
        create_move(
            label="Inside Turn(s)",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="Inside Turn(s) Into Dip",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_DIP, # TODO seeing error "FIRST_HALF_DIP" is not defined"
        ),
        create_move(
            label="Right Shoulder Duck",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="Stop at Left Shoulder",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_CATCH,
        ),
        create_move(
            label="Offer Right Hand Outside Turn(s)",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_OPPOSITE,
        ),
        create_move(
            label="Inside Turn(s) - Join Hands",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_BOTH,
        )
    ],
)

SECOND_HALF_OPPOSITE = create_position(
    label="Second Half Uncrossed Right Hand",
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.RIGHT],
    follow_hands_joined=[Direction.LEFT],
    crossed=False,
    moves=[
        create_move(
            label="Offer Left Hand Inside Turn(s)",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="J Hook Reset",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="J Hook Into Dip",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_DIP,
        ),
        create_move(
            label="Outside Turn(s)",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_OPPOSITE,
        )
    ],
)

SECOND_HALF_BOTH = create_position(
    label="Second Half Uncrossed 2 Hands",
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.LEFT, Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT, Direction.LEFT],
    crossed=False,
    moves=[
        create_move(
            label="Inside Turn(s) (Infinity)",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_BOTH,
        ),
        create_move(
            label="Spinneroo (Step to Right)",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_BOTH,
        ),
        create_move(
            label="Inside Turn - Keep Right Hand",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_BOTH_CUDDLE,
        ),
        create_move(
            label="Arm Slide",
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_CROSSED,
        ),
        create_move(
            label="Opposite Hand Arm Slide",
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_CROSSED_OPPOSITE,
        )
    ],
)

SECOND_HALF_BOTH_TWISTED = create_position(
    label="Second Half Uncrossed 2 Hands Twisted",
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.LEFT, Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT, Direction.LEFT],
    crossed=False,
    moves=[
        create_move(
            label="Hairbrush",
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_BOTH,
        ),
        create_move(
            label="Spinneroo (Step to Right)",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_BOTH,
        )
    ],
)

SECOND_HALF_BOTH_HAMMERLOCK = create_position(
    label="Second Half Hammerlock",
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.LEFT, Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT, Direction.LEFT],
    crossed=False,
    moves=[
        create_move(
            label="Hair Flip",
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_OPPOSITE,
        )
    ],
)

SECOND_HALF_CROSSED = create_position(
    label="Second Half Crossed Right Hand",
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT],
    crossed=True,
    moves=[
        create_move(
            label="Inside Turn(s) - Put Hand in Left",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="J Hook Reset",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="J Hook Into Dip",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_DIP,
        ),
        create_move(
            label="Inside Turn(s)",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_CROSSED,
        ),
        create_move(
            label="Offer Left Hand Inside Turn(s)",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_CROSSED_OPPOSITE,
        )
    ],
)

# TODO WHAT MATTERS FOR INSIDE VS OUTSIDE TURN: 
# If the hand being held during the turn is the same hand as the direction turning, then outside. 
# If hand being held is the opposite from direction turning, then inside
# TODO add inside vs. outside turn calculated properties for SubMove, but to the Move, add an optional "offered_hand" property that supersedes hand of source state
# If no offered_hand, then use hand of source state. If both hands joined on source state, ...?

SECOND_HALF_CROSSED_OPPOSITE = create_position(
    label="Second Half Crossed Left Hand",
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.LEFT],
    follow_hands_joined=[Direction.LEFT],
    crossed=True,
    moves=[
        create_move(
            label="Hairbrush",
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF,
        ),
        create_move(
            label="Offer Left Hand Inside Turn - Keep Right Hand",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_CROSSED_BOTH,
        ),
        create_move(
            label="Inside Turn - Join Hands",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_CROSSED_BOTH,
        ),
        create_move(
            label="Offer Right Hand Outside Turn(s)",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_CROSSED,
        ),
        create_move(
            label="Inside Turn(s)",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_CROSSED_OPPOSITE,
        )
    ],
)

SECOND_HALF_CROSSED_BOTH = create_position(
    label="Second Half Crossed 2 Hands",
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.LEFT, Direction.RIGHT],
    follow_hands_joined=[Direction.RIGHT, Direction.LEFT],
    crossed=True,
    moves=[
        create_move(
            label="Hairbrush",
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_BOTH,
        ),
        create_move(
            label="Sunrise",
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_BOTH,
        ),
        create_move(
            label="Spinneroo (Step to Right)",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_CROSSED_BOTH,
        )
    ],
)


# Trick/One-Off Positions
FIRST_HALF_DIP = create_position(
    label="Entering Dip",
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[],
    follow_hands_joined=[],
    crossed=False,
    moves=[
        create_move(
            label="Dip and Reset",
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF,
        )
    ],
)

FIRST_HALF_TRUST_FALL = create_position(
    label="Entering Trust Fall",
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[],
    follow_hands_joined=[],
    crossed=False,
    moves=[
        create_move(
            label="Trust Fall and Reset",
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF,
        )
    ],
)

FIRST_HALF_CATCH = create_position(
    label="First Half Catch",
    lead_start_step_foot=Direction.LEFT,
    follow_start_step_foot=Direction.RIGHT,
    lead_hands_joined=[Direction.LEFT],
    follow_hands_joined=[Direction.RIGHT],
    crossed=False,
    moves=[
        create_move(
            label="Push Into Reset",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF,
        ),
        create_move(
            label="Fishtail",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: SECOND_HALF_CATCH,
        )
    ],
)

SECOND_HALF_SHOULDER_LEAN = create_position(
    label="Second Half Shoulder Lean",
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.LEFT],
    follow_hands_joined=[Direction.LEFT],
    crossed=True,
    moves=[
        create_move(
            label="Arm Slide",
            is_lead_turn=False,
            is_follow_turn=False,
            dest_position=lambda: FIRST_HALF_OPPOSITE,
        ),
        # TODO consider a move that uses connected lead left/follow left
    ],
)

SECOND_HALF_CATCH = create_position(
    label="Second Half Catch",
    lead_start_step_foot=Direction.RIGHT,
    follow_start_step_foot=Direction.LEFT,
    lead_hands_joined=[Direction.LEFT],
    follow_hands_joined=[Direction.RIGHT],
    crossed=False,
    moves=[
        create_move(
            label="Fishtail",
            is_lead_turn=False,
            is_follow_turn=True,
            dest_position=lambda: FIRST_HALF_CATCH
        )
    ]
)


ALL_POSITIONS: list[Position] = [definition.position for definition in _POSITION_DEFINITIONS]
ALL_MOVES = _build_all_moves()
