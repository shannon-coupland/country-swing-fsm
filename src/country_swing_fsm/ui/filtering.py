from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from country_swing_fsm.enums import Difficulty, Direction, PositionType, Role
from country_swing_fsm.models import Move, Position


@dataclass(frozen=True, slots=True)
class FilterOption:
    key: str
    category: str
    section_label: str
    label: str
    predicate: Callable[[object], bool]
    opposite_key: str | None = None


@dataclass(frozen=True, slots=True)
class FilterOptions:
    position_options: tuple[FilterOption, ...]
    lead_move_options: tuple[FilterOption, ...]
    follow_move_options: tuple[FilterOption, ...]


@dataclass(frozen=True, slots=True)
class FilterResult:
    positions: list[Position]
    moves: list[Move]


def build_filter_options(
    positions: Sequence[Position],
    moves: Sequence[Move],
) -> FilterOptions:
    return FilterOptions(
        position_options=_build_position_options(positions),
        lead_move_options=_build_move_options(moves, Role.LEAD),
        follow_move_options=_build_move_options(moves, Role.FOLLOW),
    )


def filter_graph(
    all_positions: Sequence[Position],
    all_moves: Sequence[Move],
    position_options: Sequence[FilterOption],
    selected_position_keys: set[str],
    lead_move_options: Sequence[FilterOption],
    selected_lead_move_keys: set[str],
    follow_move_options: Sequence[FilterOption],
    selected_follow_move_keys: set[str],
) -> FilterResult:
    candidate_positions = [
        position
        for position in all_positions
        if _matches_selected_options(position, position_options, selected_position_keys)
    ]
    candidate_position_ids = {id(position) for position in candidate_positions}

    filtered_moves = [
        move
        for move in all_moves
        if _matches_selected_options(move, lead_move_options, selected_lead_move_keys)
        and _matches_selected_options(move, follow_move_options, selected_follow_move_keys)
        and id(move.source) in candidate_position_ids
        and id(move.destination) in candidate_position_ids
    ]

    move_filters_active = bool(selected_lead_move_keys or selected_follow_move_keys)
    if move_filters_active:
        included_position_ids = {id(move.source) for move in filtered_moves} | {
            id(move.destination) for move in filtered_moves
        }
        final_positions = [
            position for position in candidate_positions if id(position) in included_position_ids
        ]
    else:
        final_positions = candidate_positions

    return FilterResult(positions=final_positions, moves=filtered_moves)


def _matches_selected_options(
    item: object,
    options: Sequence[FilterOption],
    selected_keys: set[str],
) -> bool:
    if not selected_keys:
        return True

    selected_options = [option for option in options if option.key in selected_keys]
    categories = {option.category for option in selected_options}
    for category in categories:
        category_options = [
            option for option in selected_options if option.category == category
        ]
        if not any(option.predicate(item) for option in category_options):
            return False
    return True


def _build_position_options(positions: Sequence[Position]) -> tuple[FilterOption, ...]:
    options: list[FilterOption] = []

    for difficulty in (Difficulty.BEGINNER, Difficulty.INTERMEDIATE, Difficulty.ADVANCED):
        options.append(
            FilterOption(
                key=f"difficulty:{difficulty.value}",
                category="difficulty",
                section_label="Difficulty",
                label=difficulty.value.title(),
                predicate=lambda item, difficulty=difficulty: isinstance(item, Position)
                and item.difficulty == difficulty,
            )
        )

    available_position_types = {position.position_type for position in positions}
    for position_type in (PositionType.NORMAL, PositionType.TWISTED, PositionType.IMPACT):
        if position_type not in available_position_types:
            continue
        options.append(
            FilterOption(
                key=f"position_type:{position_type.value}",
                category="position_type",
                section_label="Position Type",
                label=position_type.value.title(),
                predicate=lambda item, position_type=position_type: isinstance(item, Position)
                and item.position_type == position_type,
            )
        )

    for crossed_value, label in ((False, "Uncrossed"), (True, "Crossed")):
        if not any(position.crossed == crossed_value for position in positions):
            continue
        options.append(
            FilterOption(
                key=f"crossed:{crossed_value}",
                category="crossed",
                section_label="Crossed",
                label=label,
                predicate=lambda item, crossed_value=crossed_value: isinstance(item, Position)
                and item.crossed == crossed_value,
                opposite_key=f"crossed:{not crossed_value}",
            )
        )

    available_hand_counts = {len(position.sub_position_for_role(Role.LEAD).hands_joined) for position in positions}
    for hand_count, label in ((0, "No Hands"), (1, "Single Hand"), (2, "Both Hands")):
        if hand_count not in available_hand_counts:
            continue
        options.append(
            FilterOption(
                key=f"hand_count:{hand_count}",
                category="hand_count",
                section_label="Hands Joined",
                label=label,
                predicate=lambda item, hand_count=hand_count: isinstance(item, Position)
                and len(item.sub_position_for_role(Role.LEAD).hands_joined) == hand_count,
            )
        )

    return tuple(options)


def _build_move_options(
    moves: Sequence[Move],
    role: Role,
) -> tuple[FilterOption, ...]:
    options: list[FilterOption] = []

    for difficulty in (Difficulty.BEGINNER, Difficulty.INTERMEDIATE, Difficulty.ADVANCED):
        options.append(
            FilterOption(
                key=f"{role.value}:difficulty:{difficulty.value}",
                category="difficulty",
                section_label="Difficulty",
                label=difficulty.value.title(),
                predicate=lambda item, difficulty=difficulty: isinstance(item, Move)
                and item.difficulty == difficulty,
            )
        )

    available_start_feet = {move.source.sub_position_for_role(role).start_step_foot for move in moves}
    for start_foot in (Direction.LEFT, Direction.RIGHT):
        if start_foot not in available_start_feet:
            continue
        options.append(
            FilterOption(
                key=f"{role.value}:start_step_foot:{start_foot.value}",
                category="start_step_foot",
                section_label="Step Start Foot",
                label=start_foot.value.title(),
                predicate=lambda item, role=role, start_foot=start_foot: isinstance(item, Move)
                and item.source.sub_position_for_role(role).start_step_foot == start_foot,
            )
        )

    available_turn_directions = {
        move.sub_move_for_role(role).turn_direction for move in moves
    }
    for turn_direction in (None, Direction.LEFT, Direction.RIGHT):
        if turn_direction not in available_turn_directions:
            continue
        options.append(
            FilterOption(
                key=(
                    f"{role.value}:turn_direction:none"
                    if turn_direction is None
                    else f"{role.value}:turn_direction:{turn_direction.value}"
                ),
                category="turn_direction",
                section_label="Turn Direction",
                label=(
                    "No Turn"
                    if turn_direction is None
                    else turn_direction.value.title()
                ),
                predicate=lambda item, role=role, turn_direction=turn_direction: isinstance(item, Move)
                and item.sub_move_for_role(role).turn_direction == turn_direction,
            )
        )

    return tuple(options)
