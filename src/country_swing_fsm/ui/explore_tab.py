from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from country_swing_fsm.enums import Direction, MoveType, PositionType, Role
from country_swing_fsm.models import Move, Position


class ExploreTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._expanded_move_keys: set[str] = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(scroll_area)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(16, 16, 16, 16)
        self._content_layout.setSpacing(12)
        self._content_layout.addStretch(1)
        scroll_area.setWidget(self._content)

    def update_content(
        self,
        *,
        visible_positions: list[Position],
        visible_moves: list[Move],
        selected_focus: tuple[str, str] | None,
        display_role: Role,
    ) -> None:
        self._clear_content()

        positions_by_key = {
            _position_option_key(position): position for position in visible_positions
        }
        moves_by_key = {_move_option_key(move): move for move in visible_moves}

        if selected_focus is None:
            self._content_layout.addWidget(QLabel("Select a position or move."))
            self._content_layout.addStretch(1)
            return

        selection_kind, selection_key = selected_focus
        if selection_kind == "move" and selection_key in moves_by_key:
            self._content_layout.addWidget(
                MoveDetailsWidget(moves_by_key[selection_key], display_role)
            )
            self._content_layout.addStretch(1)
            return

        if selection_kind == "position" and selection_key in positions_by_key:
            position = positions_by_key[selection_key]
            self._content_layout.addWidget(
                PositionDetailsWidget(
                    position=position,
                    visible_moves=visible_moves,
                    display_role=display_role,
                    expanded_move_keys=self._expanded_move_keys,
                )
            )
            self._content_layout.addStretch(1)
            return

        self._content_layout.addWidget(QLabel("Select a position or move."))
        self._content_layout.addStretch(1)

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()


class PositionDetailsWidget(QWidget):
    def __init__(
        self,
        *,
        position: Position,
        visible_moves: list[Move],
        display_role: Role,
        expanded_move_keys: set[str],
    ) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        metadata_header = QLabel("Position")
        metadata_header.setStyleSheet("font-weight: 700;")
        layout.addWidget(metadata_header)

        metadata_layout = QFormLayout()
        metadata_layout.setContentsMargins(0, 0, 0, 0)
        metadata_layout.setSpacing(6)
        metadata_layout.addRow("Label", QLabel(_display_position_label(position, display_role)))
        metadata_layout.addRow(
            "Crossed",
            QLabel("Crossed" if position.crossed else "Uncrossed"),
        )
        metadata_layout.addRow("Position Type", QLabel(_position_type_label(position.position_type)))
        layout.addLayout(metadata_layout)

        for role in (Role.LEAD, Role.FOLLOW):
            sub_position = position.sub_position_for_role(role)
            role_header = QLabel(role.value.title())
            role_header.setStyleSheet("font-weight: 700;")
            layout.addWidget(role_header)

            role_layout = QFormLayout()
            role_layout.setContentsMargins(0, 0, 0, 0)
            role_layout.setSpacing(6)
            role_layout.addRow(
                "Start Step Foot",
                QLabel(_direction_label(sub_position.start_step_foot)),
            )
            role_layout.addRow(
                "Hands Joined",
                QLabel(_hands_joined_label(sub_position.hands_joined)),
            )
            layout.addLayout(role_layout)

        outgoing_header = QLabel("Outgoing Moves")
        outgoing_header.setStyleSheet("font-weight: 700;")
        layout.addWidget(outgoing_header)

        outgoing_moves = [
            move for move in visible_moves if id(move.source) == id(position)
        ]
        if not outgoing_moves:
            layout.addWidget(QLabel("No outgoing moves."))
            return

        for move in outgoing_moves:
            layout.addWidget(
                ExpandableMoveWidget(
                    move=move,
                    display_role=display_role,
                    expanded_move_keys=expanded_move_keys,
                )
            )


class ExpandableMoveWidget(QWidget):
    def __init__(
        self,
        *,
        move: Move,
        display_role: Role,
        expanded_move_keys: set[str],
    ) -> None:
        super().__init__()
        self._move_key = _move_option_key(move)
        self._expanded_move_keys = expanded_move_keys

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        self._toggle_button = QToolButton()
        self._toggle_button.setAutoRaise(True)
        self._toggle_button.setCheckable(True)
        self._toggle_button.toggled.connect(self._on_toggled)
        row_layout.addWidget(self._toggle_button, 0, Qt.AlignmentFlag.AlignTop)

        move_label = QLabel(_move_label(move))
        row_layout.addWidget(move_label, 1)
        layout.addWidget(row)

        self._details = MoveDetailsWidget(move, display_role)
        self._details.setContentsMargins(20, 0, 0, 0)
        layout.addWidget(self._details)

        is_expanded = self._move_key in self._expanded_move_keys
        self._toggle_button.setText("▾" if is_expanded else "▴")
        self._toggle_button.setChecked(is_expanded)
        self._details.setVisible(is_expanded)

    def _on_toggled(self, checked: bool) -> None:
        if checked:
            self._expanded_move_keys.add(self._move_key)
        else:
            self._expanded_move_keys.discard(self._move_key)
        self._toggle_button.setText("▾" if checked else "▴")
        self._details.setVisible(checked)


class MoveDetailsWidget(QWidget):
    def __init__(self, move: Move, display_role: Role) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # header = QLabel("Move")
        # header.setStyleSheet("font-weight: 700;")
        # layout.addWidget(header)

        metadata_layout = QFormLayout()
        metadata_layout.setContentsMargins(0, 0, 0, 0)
        metadata_layout.setSpacing(6)
        metadata_layout.addRow("Label", QLabel(_move_label(move)))
        metadata_layout.addRow(
            "Source Position",
            QLabel(_position_reference_label(move.source, display_role)),
        )
        metadata_layout.addRow(
            "Destination Position",
            QLabel(_position_reference_label(move.destination, display_role)),
        )
        metadata_layout.addRow("Move Type", QLabel(_move_type_label(move.move_type)))
        metadata_layout.addRow(
            "Lead Turn Direction",
            QLabel(_turn_direction_label(move.sub_move_for_role(Role.LEAD).turn_direction)),
        )
        metadata_layout.addRow(
            "Follow Turn Direction",
            QLabel(_turn_direction_label(move.sub_move_for_role(Role.FOLLOW).turn_direction)),
        )
        layout.addLayout(metadata_layout)


def _display_position_label(position: Position, display_role: Role) -> str:
    if position.label:
        return position.label
    return _generated_position_label(position, display_role)


def _generated_position_label(position: Position, display_role: Role) -> str:
    sub_position = position.sub_position_for_role(display_role)
    step_label = f"{sub_position.start_step_foot.value.title()} Step"
    hands_label = _hands_joined_label(sub_position.hands_joined)
    if not sub_position.hands_joined:
        label = f"{step_label} {hands_label}"
    else:
        crossed_label = "Crossed" if position.crossed else "Uncrossed"
        label = f"{step_label} {crossed_label} {hands_label}"

    if position.position_type == PositionType.TWISTED:
        return f"{label} Twisted"
    return label


def _hands_joined_label(hands_joined: list[Direction]) -> str:
    if len(hands_joined) == 2:
        return "Both Hands"
    if len(hands_joined) == 1:
        return f"{hands_joined[0].value.title()} Hand"
    return "No Hands"


def _position_type_label(position_type: PositionType) -> str:
    return position_type.value.replace("_", " ").title()


def _move_type_label(move_type: MoveType) -> str:
    if move_type == MoveType.OFFER_OR_DROP:
        return "Offer/Drop"
    return move_type.value.replace("_", " ").title()


def _direction_label(direction: Direction) -> str:
    return direction.value.title()


def _turn_direction_label(direction: Direction | None) -> str:
    if direction is None:
        return "N/A"
    return _direction_label(direction)


def _move_label(move: Move) -> str:
    return move.label or "(unlabeled)"


def _position_reference_label(position: Position, display_role: Role) -> str:
    return f"{position.position_id} - {_display_position_label(position, display_role)}"


def _position_option_key(position: Position) -> str:
    return f"position:{id(position)}"


def _move_option_key(move: Move) -> str:
    return f"move:{id(move)}"
