from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QAction, QBrush, QColor, QPainter, QPainterPath, QPen, QPolygonF, QTransform
from PySide6.QtWidgets import (
    QCheckBox,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from country_swing_fsm.enums import Direction, PositionType, Role
from country_swing_fsm.models import Move, Position
from country_swing_fsm.ui.filtering import FilterOption, FilterOptions, build_filter_options, filter_graph


LEFT_COLOR = QColor("#2563eb")
RIGHT_COLOR = QColor("#f97316")
IMPACT_COLOR = QColor("#9333ea")
BACKGROUND_COLOR = QColor("#f8fafc")
TOP_BAR_COLOR = QColor("#e2e8f0")
TEXT_COLOR = QColor("#0f172a")
LEAD_DIAGRAM_COLOR = QColor("#ec4899")
FOLLOW_DIAGRAM_COLOR = QColor("#22c55e")
DIAGRAM_LINE_COLOR = QColor("#334155")
DIAGRAM_LINE_OUTLINE_COLOR = QColor("#ffffff")

CIRCLE_DIAMETER = 120.0
LEFT_COLUMN_X = 120.0
RIGHT_COLUMN_X = 680.0
IMPACT_START_X = 220.0
IMPACT_SPACING = 180.0
TOP_MARGIN = 80.0
ROW_SPACING = 220.0
GROUPED_ROW_SPACING = max(ROW_SPACING / 3.0, CIRCLE_DIAMETER + 24.0)
DIMMED_OPACITY = 0.18
SELECTION_KIND_DATA_KEY = 0
SELECTION_ID_DATA_KEY = 1
OUTER_CIRCLE_PEN_WIDTH = 3.0
INNER_CIRCLE_DIAMETER = 28.0
INNER_CIRCLE_RADIUS = INNER_CIRCLE_DIAMETER / 2.0
INNER_CIRCLE_VERTICAL_OFFSET = 22.0
INNER_CIRCLE_TEXT_SIZE = 12.0
CONNECTION_PEN_WIDTH = 3.0
CONNECTION_OUTLINE_PEN_WIDTH = 7.0

GROUP_ORDER = {
    (False, 1): 0,
    (False, 2): 1,
    (True, 1): 2,
    (True, 2): 3,
}
POSITION_TYPE_ORDER = {
    PositionType.NORMAL: 0,
    PositionType.TWISTED: 1,
    PositionType.IMPACT: 2,
}
DIRECTION_ORDER = {
    Direction.LEFT: 0,
    Direction.RIGHT: 1,
}
FILTER_BUTTON_TITLES = {
    "position_types": "Position Types",
    "lead_moves": "Lead Moves",
    "follow_moves": "Follow Moves",
}


class MainWindow(QMainWindow):
    def __init__(self, positions: list[Position], moves: list[Move]) -> None:
        super().__init__()
        self.all_positions = positions
        self.all_moves = moves
        self.filter_options = build_filter_options(positions, moves)
        self.selected_filter_keys: dict[str, set[str]] = {
            "position_types": set(),
            "lead_moves": set(),
            "follow_moves": set(),
        }
        self.filter_buttons: dict[str, QToolButton] = {}
        self.filter_actions: dict[str, list[QAction]] = {}
        self.position_button: QToolButton | None = None
        self.position_actions_by_key: dict[str, QAction] = {}
        self.position_lookup_by_key: dict[str, Position] = {
            _position_option_key(position): position for position in self.all_positions
        }
        self.visible_position_keys: set[str] = set(self.position_lookup_by_key)
        self.display_role = Role.LEAD
        self.offer_hand_passthrough = False
        self.selected_focus: tuple[str, str] | None = None
        self.filter_options_by_key: dict[str, FilterOption] = {
            option.key: option
            for option in (
                *self.filter_options.position_options,
                *self.filter_options.lead_move_options,
                *self.filter_options.follow_move_options,
            )
        }
        self._suppress_refresh = False

        self.setWindowTitle("Country Swing FSM")
        self.resize(1000, 700)

        self.view = DiagramView(QGraphicsScene())

        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self._build_filter_bar())
        central_layout.addWidget(self.view)
        self.setCentralWidget(central_widget)

        self._refresh_scene()

    def _build_filter_bar(self) -> QWidget:
        bar = QWidget()
        bar.setAutoFillBackground(True)
        palette = bar.palette()
        palette.setColor(bar.backgroundRole(), TOP_BAR_COLOR)
        bar.setPalette(palette)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        mode_container = QWidget()
        mode_layout = QHBoxLayout(mode_container)
        mode_layout.setContentsMargins(0, 0, 8, 0)
        mode_layout.setSpacing(6)
        lead_mode_label = QLabel("Lead Mode")
        lead_mode_label.setStyleSheet(
            f"color: {LEAD_DIAGRAM_COLOR.name()}; font-weight: 700;"
        )
        mode_layout.addWidget(lead_mode_label)
        mode_slider = ModeToggleSlider()
        mode_slider.setRange(0, 1)
        mode_slider.setValue(0)
        mode_slider.setFixedWidth(42)
        mode_slider.setSingleStep(1)
        mode_slider.setPageStep(1)
        mode_slider.setTickInterval(1)
        mode_slider.valueChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(mode_slider)
        follow_mode_label = QLabel("Follow Mode")
        follow_mode_label.setStyleSheet(
            f"color: {FOLLOW_DIAGRAM_COLOR.name()}; font-weight: 700;"
        )
        mode_layout.addWidget(follow_mode_label)
        layout.addWidget(mode_container)

        self._add_position_selector_button(layout)
        self._add_filter_button(
            layout,
            "position_types",
            self.filter_options.position_options,
        )
        self._add_filter_button(
            layout,
            "lead_moves",
            self.filter_options.lead_move_options,
        )
        self._add_filter_button(
            layout,
            "follow_moves",
            self.filter_options.follow_move_options,
        )
        clear_button = QPushButton("Clear All Filters")
        clear_button.clicked.connect(self._clear_all_filters)
        layout.addWidget(clear_button)
        layout.addStretch(1)
        offer_hand_passthrough_checkbox = QCheckBox("Offer Hand Passthrough")
        offer_hand_passthrough_checkbox.toggled.connect(self._on_offer_hand_passthrough_toggled)
        layout.addWidget(offer_hand_passthrough_checkbox)
        return bar

    def _add_position_selector_button(self, layout: QHBoxLayout) -> None:
        button = QToolButton()
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setAutoRaise(True)
        button.setStyleSheet("QToolButton { padding: 4px 10px; }")

        menu = PersistentFilterMenu(button)
        for position in self._sorted_position_selector_positions():
            position_key = _position_option_key(position)
            action = QAction(_display_position_label(position, self.display_role), menu)
            action.setCheckable(True)
            action.setChecked(True)
            action.setData(position_key)
            action.toggled.connect(
                lambda checked, position_key=position_key: self._on_position_visibility_toggled(
                    position_key,
                    checked,
                )
            )
            menu.addAction(action)
            self.position_actions_by_key[position_key] = action

        button.setMenu(menu)
        self.position_button = button
        self._update_position_selector_label()
        layout.addWidget(button)

    def _add_filter_button(
        self,
        layout: QHBoxLayout,
        filter_key: str,
        options: tuple[FilterOption, ...],
    ) -> None:
        button = QToolButton()
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setAutoRaise(True)
        button.setStyleSheet("QToolButton { padding: 4px 10px; }")
        self.filter_actions[filter_key] = []

        menu = PersistentFilterMenu(button)
        previous_section_label: str | None = None
        for option in options:
            if previous_section_label != option.section_label:
                if previous_section_label is not None:
                    menu.addSeparator()
                header_action = QAction(option.section_label, menu)
                header_action.setEnabled(False)
                menu.addAction(header_action)
                previous_section_label = option.section_label

            action = QAction(option.label, menu)
            action.setCheckable(True)
            action.setData(option.key)
            action.toggled.connect(
                lambda checked, filter_key=filter_key, option_key=option.key: self._on_filter_toggled(
                    filter_key,
                    option_key,
                    checked,
                )
            )
            menu.addAction(action)
            self.filter_actions[filter_key].append(action)

        button.setMenu(menu)
        self.filter_buttons[filter_key] = button
        self._update_filter_button_label(filter_key)
        layout.addWidget(button)

    def _on_filter_toggled(self, filter_key: str, option_key: str, checked: bool) -> None:
        selected_keys = self.selected_filter_keys[filter_key]
        if checked:
            selected_keys.add(option_key)
            opposite_key = self.filter_options_by_key[option_key].opposite_key
            if opposite_key is not None and opposite_key in selected_keys:
                selected_keys.discard(opposite_key)
                self._suppress_refresh = True
                try:
                    self._set_action_checked(filter_key, opposite_key, False)
                finally:
                    self._suppress_refresh = False
        else:
            selected_keys.discard(option_key)
        self._update_filter_button_label(filter_key)
        if not self._suppress_refresh:
            self._refresh_scene()

    def _on_position_visibility_toggled(self, position_key: str, checked: bool) -> None:
        if checked:
            self.visible_position_keys.add(position_key)
        else:
            self.visible_position_keys.discard(position_key)
        self._update_position_selector_label()
        if not self._suppress_refresh:
            self._refresh_scene()

    def _clear_all_filters(self) -> None:
        self._suppress_refresh = True
        try:
            for filter_key, selected_keys in self.selected_filter_keys.items():
                selected_keys.clear()
                for action in self.filter_actions[filter_key]:
                    if action.isChecked():
                        action.setChecked(False)
                self._update_filter_button_label(filter_key)
            self.visible_position_keys = set(self.position_lookup_by_key)
            for action in self.position_actions_by_key.values():
                if not action.isChecked():
                    action.setChecked(True)
            self._update_position_selector_label()
        finally:
            self._suppress_refresh = False

        self._refresh_scene()

    def _set_action_checked(self, filter_key: str, option_key: str, checked: bool) -> None:
        for action in self.filter_actions[filter_key]:
            if action.data() == option_key and action.isChecked() != checked:
                action.setChecked(checked)
                return

    def _update_filter_button_label(self, filter_key: str) -> None:
        base_title = FILTER_BUTTON_TITLES[filter_key]
        selected_count = len(self.selected_filter_keys[filter_key])
        label = base_title if selected_count == 0 else f"{base_title} ({selected_count})"
        self.filter_buttons[filter_key].setText(label)

    def _update_position_selector_label(self) -> None:
        if self.position_button is None:
            return

        total_count = len(self.position_lookup_by_key)
        visible_count = len(self.visible_position_keys)
        if visible_count == total_count:
            label = "Positions"
        else:
            label = f"Positions ({visible_count})"
        self.position_button.setText(label)

    def _on_mode_changed(self, value: int) -> None:
        self.display_role = Role.FOLLOW if value == 1 else Role.LEAD
        self._update_position_action_labels()
        self._refresh_scene(preserve_view=True)

    def _on_offer_hand_passthrough_toggled(self, checked: bool) -> None:
        self.offer_hand_passthrough = checked
        self._refresh_scene(preserve_view=True)

    def _refresh_scene(self, preserve_view: bool = False) -> None:
        visible_positions = [
            position
            for position_key, position in self.position_lookup_by_key.items()
            if position_key in self.visible_position_keys
        ]
        visible_position_ids = {id(position) for position in visible_positions}
        visible_moves = [
            move
            for move in self.all_moves
            if id(move.source) in visible_position_ids and id(move.destination) in visible_position_ids
            and (self.offer_hand_passthrough or not _is_same_side_move(move))
        ]
        filtered_graph = filter_graph(
            all_positions=visible_positions,
            all_moves=visible_moves,
            position_options=self.filter_options.position_options,
            selected_position_keys=self.selected_filter_keys["position_types"],
            lead_move_options=self.filter_options.lead_move_options,
            selected_lead_move_keys=self.selected_filter_keys["lead_moves"],
            follow_move_options=self.filter_options.follow_move_options,
            selected_follow_move_keys=self.selected_filter_keys["follow_moves"],
        )
        self.view.load_scene(
            build_scene(
                filtered_graph.positions,
                filtered_graph.moves,
                display_role=self.display_role,
                selected_focus=self.selected_focus,
                offer_hand_passthrough=self.offer_hand_passthrough,
                on_focus_change=self._on_focus_change,
            ),
            preserve_view=preserve_view,
        )

    def _update_position_action_labels(self) -> None:
        for position_key, action in self.position_actions_by_key.items():
            action.setText(
                _display_position_label(
                    self.position_lookup_by_key[position_key],
                    self.display_role,
                )
            )

    def _sorted_position_selector_positions(self) -> list[Position]:
        left_positions = _sorted_column_positions(
            [
                position
                for position in self.all_positions
                if (
                    position.position_type != PositionType.IMPACT
                    and position.lead_start_step_foot == Direction.LEFT
                )
            ]
        )
        right_positions = _sorted_column_positions(
            [
                position
                for position in self.all_positions
                if (
                    position.position_type != PositionType.IMPACT
                    and position.lead_start_step_foot == Direction.RIGHT
                )
            ]
        )
        impact_positions = _sorted_impact_positions(
            [position for position in self.all_positions if position.position_type == PositionType.IMPACT]
        )
        return [*left_positions, *right_positions, *impact_positions]

    def _on_focus_change(self, selected_focus: tuple[str, str] | None) -> None:
        if self.selected_focus == selected_focus:
            return
        self.selected_focus = selected_focus
        self._refresh_scene(preserve_view=True)


class DiagramView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        self._has_manual_zoom = False
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setBackgroundBrush(BACKGROUND_COLOR)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._has_manual_zoom:
            self._fit_scene()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._has_manual_zoom:
            self._fit_scene()

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._has_manual_zoom = True
            zoom_in_factor = 1.15
            zoom_factor = zoom_in_factor if event.angleDelta().y() > 0 else 1.0 / zoom_in_factor

            old_anchor = self.transformationAnchor()
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
            self.scale(zoom_factor, zoom_factor)
            self.setTransformationAnchor(old_anchor)
            event.accept()
            return

        super().wheelEvent(event)

    def load_scene(self, scene: QGraphicsScene, preserve_view: bool = False) -> None:
        previous_transform = self.transform()
        previous_center = self.mapToScene(self.viewport().rect().center())

        if not preserve_view:
            self._has_manual_zoom = False

        self.setScene(scene)
        if preserve_view:
            self.setTransform(previous_transform)
            self.centerOn(previous_center)
            return

        self._fit_scene()

    def _fit_scene(self) -> None:
        rect = self.sceneRect()
        if rect.isValid() and not rect.isEmpty():
            self.resetTransform()
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)


class PersistentFilterMenu(QMenu):
    def mouseReleaseEvent(self, event) -> None:
        action = self.activeAction()
        if action is not None and action.isCheckable():
            action.trigger()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class InteractiveScene(QGraphicsScene):
    def __init__(
        self,
        on_focus_change: Callable[[tuple[str, str] | None], None] | None = None,
    ) -> None:
        super().__init__()
        self._on_focus_change = on_focus_change

    def mousePressEvent(self, event) -> None:
        clicked_item = self.itemAt(event.scenePos(), QTransform())
        selection = _selection_for_item(clicked_item)
        if self._on_focus_change is not None:
            self._on_focus_change(selection)
        super().mousePressEvent(event)


class ModeToggleSlider(QSlider):
    def __init__(self) -> None:
        super().__init__(Qt.Orientation.Horizontal)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setValue(0 if self.value() == 1 else 1)
            event.accept()
            return
        super().mousePressEvent(event)


def build_scene(
    positions: list[Position],
    moves: list[Move],
    display_role: Role = Role.LEAD,
    selected_focus: tuple[str, str] | None = None,
    offer_hand_passthrough: bool = False,
    on_focus_change: Callable[[tuple[str, str] | None], None] | None = None,
) -> QGraphicsScene:
    scene = InteractiveScene(on_focus_change=on_focus_change)
    scene.setBackgroundBrush(BACKGROUND_COLOR)

    included_positions_by_id = {id(position): position for position in positions}
    filtered_moves = [
        move
        for move in moves
        if id(move.source) in included_positions_by_id and id(move.destination) in included_positions_by_id
    ]

    left_positions = _sorted_column_positions(
        [
            position
            for position in positions
            if (
                position.position_type != PositionType.IMPACT
                and position.lead_start_step_foot == Direction.LEFT
            )
        ]
    )
    right_positions = _sorted_column_positions(
        [
            position
            for position in positions
            if (
                position.position_type != PositionType.IMPACT
                and position.lead_start_step_foot == Direction.RIGHT
            )
        ]
    )
    impact_positions = _sorted_impact_positions(
        [position for position in positions if position.position_type == PositionType.IMPACT]
    )
    impact_row_width = (max(len(impact_positions) - 1, 0)) * IMPACT_SPACING
    right_column_x = max(
        RIGHT_COLUMN_X,
        (2.0 * IMPACT_START_X) + impact_row_width - LEFT_COLUMN_X,
    )

    centers_by_position_id: dict[int, QPointF] = {}
    position_items_by_key: dict[str, list[QGraphicsItem]] = {}
    move_items_by_key: dict[str, list[QGraphicsItem]] = {}

    _add_column_header(scene, "Lead starts LEFT", LEFT_COLUMN_X, LEFT_COLOR)
    _add_column_header(scene, "Lead starts RIGHT", right_column_x, RIGHT_COLOR)

    left_y_positions, right_y_positions = _aligned_column_y_positions(
        left_positions,
        right_positions,
    )

    for index, position in enumerate(left_positions):
        center = QPointF(LEFT_COLUMN_X, left_y_positions[index])
        centers_by_position_id[id(position)] = center
        position_key = _position_option_key(position)
        position_items_by_key[position_key] = _add_position_node(
            scene,
            position,
            center,
            LEFT_COLOR,
            display_role,
            position_key,
        )

    for index, position in enumerate(right_positions):
        center = QPointF(right_column_x, right_y_positions[index])
        centers_by_position_id[id(position)] = center
        position_key = _position_option_key(position)
        position_items_by_key[position_key] = _add_position_node(
            scene,
            position,
            center,
            RIGHT_COLOR,
            display_role,
            position_key,
        )

    impact_row_start_x = ((LEFT_COLUMN_X + right_column_x) / 2.0) - (impact_row_width / 2.0)
    impact_row_y = max(
        left_y_positions[-1] if left_y_positions else 0.0,
        right_y_positions[-1] if right_y_positions else 0.0,
    ) + ROW_SPACING

    for index, position in enumerate(impact_positions):
        center = QPointF(impact_row_start_x + (index * IMPACT_SPACING), impact_row_y)
        centers_by_position_id[id(position)] = center
        position_key = _position_option_key(position)
        position_items_by_key[position_key] = _add_position_node(
            scene,
            position,
            center,
            IMPACT_COLOR,
            display_role,
            position_key,
        )

    parallel_move_groups: dict[tuple[int, int], list[Move]] = {}
    for move in filtered_moves:
        key = (id(move.source), id(move.destination))
        parallel_move_groups.setdefault(key, []).append(move)

    for sibling_moves in parallel_move_groups.values():
        move = sibling_moves[0]
        move_key = _move_option_key(move)
        move_items_by_key[move_key] = _add_move_edge(
            scene=scene,
            move=move,
            source_center=centers_by_position_id[id(move.source)],
            destination_center=centers_by_position_id[id(move.destination)],
            label="\n".join(sibling_move.label or "(unlabeled)" for sibling_move in sibling_moves),
            move_key=move_key,
        )

    _apply_focus_state(
        position_items_by_key=position_items_by_key,
        move_items_by_key=move_items_by_key,
        positions_by_key={_position_option_key(position): position for position in positions},
        moves_by_key={_move_option_key(move): move for move in filtered_moves},
        selected_focus=selected_focus,
        offer_hand_passthrough=offer_hand_passthrough,
    )

    scene.setSceneRect(scene.itemsBoundingRect().adjusted(-80.0, -60.0, 80.0, 60.0))
    return scene


def _sorted_column_positions(positions: list[Position]) -> list[Position]:
    return sorted(positions, key=_column_position_sort_key)


def _sorted_impact_positions(positions: list[Position]) -> list[Position]:
    return sorted(
        positions,
        key=lambda position: (
            POSITION_TYPE_ORDER[position.position_type],
            DIRECTION_ORDER[position.lead_start_step_foot],
            _hands_joined_sort_key(position),
            position.label or "",
        ),
    )


def _column_position_sort_key(position: Position) -> tuple[int, int, tuple[int, ...], str]:
    return (
        GROUP_ORDER.get(
            (position.crossed, len(position.sub_position_for_role(Role.LEAD).hands_joined)),
            len(GROUP_ORDER),
        ),
        POSITION_TYPE_ORDER[position.position_type],
        _single_hand_priority(position),
        _hands_joined_sort_key(position),
        position.label or "",
    )


def _hands_joined_sort_key(position: Position) -> tuple[int, ...]:
    return tuple(
        DIRECTION_ORDER[direction]
        for direction in position.sub_position_for_role(Role.LEAD).hands_joined
    )


def _single_hand_priority(position: Position) -> int:
    follow_hands_joined = position.sub_position_for_role(Role.FOLLOW).hands_joined
    if len(follow_hands_joined) != 1:
        return 0
    return 0 if follow_hands_joined[0] == Direction.RIGHT else 1


def _aligned_column_y_positions(
    left_positions: list[Position],
    right_positions: list[Position],
) -> tuple[list[float], list[float]]:
    left_groups = _display_groups(left_positions)
    right_groups = _display_groups(right_positions)

    left_y_positions: list[float] = []
    right_y_positions: list[float] = []
    group_start_y = TOP_MARGIN + 80.0
    group_count = max(len(left_groups), len(right_groups))

    for group_index in range(group_count):
        left_group = left_groups[group_index] if group_index < len(left_groups) else []
        right_group = right_groups[group_index] if group_index < len(right_groups) else []

        left_y_positions.extend(_group_y_positions(left_group, group_start_y))
        right_y_positions.extend(_group_y_positions(right_group, group_start_y))

        tallest_group_height = max(
            _group_height(left_group),
            _group_height(right_group),
        )
        group_start_y += tallest_group_height + ROW_SPACING

    return left_y_positions, right_y_positions


def _display_groups(positions: list[Position]) -> list[list[Position]]:
    grouped_positions: dict[int, list[Position]] = {}
    for position in positions:
        group_index = GROUP_ORDER.get(
            (position.crossed, len(position.sub_position_for_role(Role.LEAD).hands_joined)),
            len(GROUP_ORDER),
        )
        grouped_positions.setdefault(group_index, []).append(position)

    return [grouped_positions[index] for index in sorted(grouped_positions)]


def _group_y_positions(group: list[Position], start_y: float) -> list[float]:
    return [start_y + (index * GROUPED_ROW_SPACING) for index in range(len(group))]


def _group_height(group: list[Position]) -> float:
    return max(len(group) - 1, 0) * GROUPED_ROW_SPACING


def _add_column_header(scene: QGraphicsScene, label: str, center_x: float, color: QColor) -> None:
    text_item = QGraphicsSimpleTextItem(label)
    text_item.setBrush(QBrush(color))
    bounds = text_item.boundingRect()
    text_item.setPos(center_x - (bounds.width() / 2.0), 20.0)
    scene.addItem(text_item)


def _add_position_node(
    scene: QGraphicsScene,
    position: Position,
    center: QPointF,
    outline_color: QColor,
    display_role: Role,
    position_key: str,
) -> list[QGraphicsItem]:
    circle_rect = QRectF(
        center.x() - (CIRCLE_DIAMETER / 2.0),
        center.y() - (CIRCLE_DIAMETER / 2.0),
        CIRCLE_DIAMETER,
        CIRCLE_DIAMETER,
    )
    circle = QGraphicsEllipseItem(circle_rect)
    circle.setBrush(QBrush(Qt.BrushStyle.NoBrush))
    circle.setPen(QPen(outline_color, OUTER_CIRCLE_PEN_WIDTH))
    _set_item_focus_data(circle, "position", position_key)
    scene.addItem(circle)

    items: list[QGraphicsItem] = [circle]
    if position.position_type == PositionType.NORMAL:
        items.extend(_add_normal_position_diagram(scene, position, center, display_role, position_key))
        return items

    label = _display_position_label(position, display_role)
    text_item = QGraphicsTextItem(label)
    text_item.setDefaultTextColor(TEXT_COLOR)
    text_item.setTextWidth(CIRCLE_DIAMETER - 20.0)
    text_item.document().setDocumentMargin(0.0)
    bounds = text_item.boundingRect()
    text_item.setPos(center.x() - (bounds.width() / 2.0), center.y() - (bounds.height() / 2.0))
    _set_item_focus_data(text_item, "position", position_key)
    scene.addItem(text_item)
    items.append(text_item)
    return items


def _add_normal_position_diagram(
    scene: QGraphicsScene,
    position: Position,
    center: QPointF,
    display_role: Role,
    position_key: str,
) -> list[QGraphicsItem]:
    bottom_role = display_role
    top_role = Role.FOLLOW if display_role == Role.LEAD else Role.LEAD
    top_center = QPointF(center.x(), center.y() - INNER_CIRCLE_VERTICAL_OFFSET)
    bottom_center = QPointF(center.x(), center.y() + INNER_CIRCLE_VERTICAL_OFFSET)
    centers_by_role = {
        top_role: top_center,
        bottom_role: bottom_center,
    }

    items: list[QGraphicsItem] = []
    items.extend(
        _add_hand_connection_items(
            scene,
            position,
            centers_by_role,
            display_role,
            position_key,
        )
    )
    items.extend(
        _add_role_circle_items(
            scene,
            position.sub_position_for_role(top_role),
            top_center,
            _diagram_role_color(top_role),
            position_key,
        )
    )
    items.extend(
        _add_role_circle_items(
            scene,
            position.sub_position_for_role(bottom_role),
            bottom_center,
            _diagram_role_color(bottom_role),
            position_key,
        )
    )
    return items


def _add_hand_connection_items(
    scene: QGraphicsScene,
    position: Position,
    centers_by_role: dict[Role, QPointF],
    display_role: Role,
    position_key: str,
) -> list[QGraphicsItem]:
    lead_hands = position.sub_position_for_role(Role.LEAD).hands_joined
    follow_sub_position = position.sub_position_for_role(Role.FOLLOW)
    follow_hands = follow_sub_position.hands_joined
    hand_count = len(lead_hands)
    if hand_count == 0:
        return []

    outline_pen = QPen(DIAGRAM_LINE_OUTLINE_COLOR, CONNECTION_OUTLINE_PEN_WIDTH)
    pen = QPen(DIAGRAM_LINE_COLOR, CONNECTION_PEN_WIDTH)
    connection_specs: list[tuple[Direction, QPointF, QPointF]] = []
    items: list[QGraphicsItem] = []
    for index, lead_hand in enumerate(lead_hands):
        follow_index = hand_count - 1 - index if hand_count == 2 and position.crossed else index
        follow_hand = follow_hands[follow_index]
        lead_point = _hand_anchor_point(
            Role.LEAD,
            lead_hand,
            centers_by_role[Role.LEAD],
            display_role,
        )
        follow_point = _hand_anchor_point(
            Role.FOLLOW,
            follow_hand,
            centers_by_role[Role.FOLLOW],
            display_role,
        )
        connection_specs.append((follow_hand, lead_point, follow_point))

    if hand_count == 2:
        start_foot_hand = follow_sub_position.start_step_foot
        connection_specs.sort(
            key=lambda connection_spec: connection_spec[0] == start_foot_hand
        )

    for _, lead_point, follow_point in connection_specs:
        outline_item = scene.addLine(
            lead_point.x(),
            lead_point.y(),
            follow_point.x(),
            follow_point.y(),
            outline_pen,
        )
        _set_item_focus_data(outline_item, "position", position_key)
        items.append(outline_item)

        line_item = scene.addLine(
            lead_point.x(),
            lead_point.y(),
            follow_point.x(),
            follow_point.y(),
            pen,
        )
        _set_item_focus_data(line_item, "position", position_key)
        items.append(line_item)
    return items


def _add_role_circle_items(
    scene: QGraphicsScene,
    sub_position,
    center: QPointF,
    fill_color: QColor,
    position_key: str,
) -> list[QGraphicsItem]:
    rect = QRectF(
        center.x() - INNER_CIRCLE_RADIUS,
        center.y() - INNER_CIRCLE_RADIUS,
        INNER_CIRCLE_DIAMETER,
        INNER_CIRCLE_DIAMETER,
    )
    circle = QGraphicsEllipseItem(rect)
    circle.setBrush(QBrush(fill_color))
    circle.setPen(QPen(fill_color.darker(115), 1.5))
    _set_item_focus_data(circle, "position", position_key)
    scene.addItem(circle)

    text_item = QGraphicsSimpleTextItem(
        "LS" if sub_position.start_step_foot == Direction.LEFT else "RS"
    )
    text_item.setBrush(QBrush(TEXT_COLOR))
    font = text_item.font()
    font.setPointSizeF(INNER_CIRCLE_TEXT_SIZE)
    font.setBold(True)
    text_item.setFont(font)
    bounds = text_item.boundingRect()
    text_item.setPos(center.x() - (bounds.width() / 2.0), center.y() - (bounds.height() / 2.0))
    _set_item_focus_data(text_item, "position", position_key)
    scene.addItem(text_item)
    return [circle, text_item]


def _hand_anchor_point(
    role: Role,
    hand: Direction,
    circle_center: QPointF,
    display_role: Role,
) -> QPointF:
    side_multiplier = 1.0 if hand == Direction.RIGHT else -1.0
    if role == Role.FOLLOW:
        side_multiplier *= -1.0
    if display_role == Role.FOLLOW:
        side_multiplier *= -1.0
    return QPointF(circle_center.x() + (INNER_CIRCLE_RADIUS * side_multiplier), circle_center.y())


def _diagram_role_color(role: Role) -> QColor:
    return LEAD_DIAGRAM_COLOR if role == Role.LEAD else FOLLOW_DIAGRAM_COLOR


def _display_position_label(position: Position, display_role: Role) -> str:
    generated_label = _generated_position_label(position, display_role)
    if position.label:
        return f"{position.label} - {generated_label}"
    return generated_label


def _generated_position_label(position: Position, display_role: Role) -> str:
    sub_position = position.sub_position_for_role(display_role)
    step_label = f"{sub_position.start_step_foot.value.title()} Step"
    hands_label = _generated_hands_label(sub_position.hands_joined)
    if not sub_position.hands_joined:
        return f"{step_label} {hands_label}"
    crossed_label = "Crossed" if position.crossed else "Uncrossed"
    return f"{step_label} {crossed_label} {hands_label}"


def _generated_hands_label(hands_joined: list[Direction]) -> str:
    if len(hands_joined) == 2:
        return "Both Hands"
    if len(hands_joined) == 1:
        return f"{hands_joined[0].value.title()} Hand"
    return "No Hands"


def _position_option_key(position: Position) -> str:
    return f"position:{id(position)}"


def _move_option_key(move: Move) -> str:
    return f"move:{id(move.source)}:{id(move.destination)}"


def _add_move_edge(
    scene: QGraphicsScene,
    move: Move,
    source_center: QPointF,
    destination_center: QPointF,
    label: str,
    move_key: str,
) -> list[QGraphicsItem]:
    if move.source.position_type == PositionType.IMPACT:
        color = IMPACT_COLOR
    else:
        color = LEFT_COLOR if move.source.lead_start_step_foot == Direction.LEFT else RIGHT_COLOR
    pen = QPen(color, 3)

    start_quadrant, end_quadrant, start_direction, end_direction = _edge_routing(
        move.source,
        move.destination,
    )
    start = _circle_quadrant_point(source_center, start_quadrant)
    end = _circle_quadrant_point(destination_center, end_quadrant)
    path = _build_edge_path(
        start=start,
        end=end,
        start_direction=start_direction,
        end_direction=end_direction,
        curvature_offset=_curvature_offset(
            source_center=source_center,
            destination_center=destination_center,
        ),
    )

    path_item = QGraphicsPathItem(path)
    path_item.setPen(pen)
    _set_item_focus_data(path_item, "move", move_key)
    scene.addItem(path_item)

    arrow_item = _add_arrow_head(scene, path, color, move_key)
    label_item = _add_edge_label(scene, label, path, color, source_center, move_key)
    return [path_item, arrow_item, label_item]


def _circle_quadrant_point(center: QPointF, quadrant: str) -> QPointF:
    radius = CIRCLE_DIAMETER / 2.0
    horizontal_offset = (3.0**0.5 / 2.0) * radius
    vertical_offset = 0.5 * radius

    quadrant_offsets = {
        "top_left": (-horizontal_offset, -vertical_offset),
        "top_right": (horizontal_offset, -vertical_offset),
        "bottom_left": (-horizontal_offset, vertical_offset),
        "bottom_right": (horizontal_offset, vertical_offset),
    }
    x_offset, y_offset = quadrant_offsets[quadrant]
    return QPointF(center.x() + x_offset, center.y() + y_offset)


def _build_edge_path(
    start: QPointF,
    end: QPointF,
    start_direction: str,
    end_direction: str,
    curvature_offset: float,
) -> QPainterPath:
    path = QPainterPath(start)
    control_offset = max(abs(end.x() - start.x()) * 0.25, 70.0)
    start_sign = 1.0 if start_direction == "right" else -1.0
    end_sign = 1.0 if end_direction == "right" else -1.0
    control_one = QPointF(
        start.x() + (control_offset * start_sign),
        start.y() + curvature_offset,
    )
    control_two = QPointF(
        end.x() - (control_offset * end_sign),
        end.y() + curvature_offset,
    )
    path.cubicTo(control_one, control_two, end)
    return path


def _edge_routing(
    source: Position,
    destination: Position,
) -> tuple[str, str, str, str]:
    source_side = _position_side(source)
    destination_side = _position_side(destination)

    routing_table = {
        ("left", "right"): ("top_right", "top_left", "right", "right"),
        ("left", "left"): ("top_left", "bottom_left", "left", "right"),
        ("left", "impact"): ("top_right", "top_left", "right", "right"),
        ("right", "left"): ("bottom_left", "bottom_right", "left", "left"),
        ("right", "right"): ("top_right", "bottom_right", "right", "left"),
        ("right", "impact"): ("bottom_left", "top_right", "left", "left"),
        ("impact", "left"): ("top_left", "bottom_right", "left", "left"),
        ("impact", "right"): ("top_right", "top_left", "right", "right"),
    }
    return routing_table.get(
        (source_side, destination_side),
        ("top_right", "top_left", "right", "right"),
    )


def _position_side(position: Position) -> str:
    if position.position_type == PositionType.IMPACT:
        return "impact"
    if position.lead_start_step_foot == Direction.LEFT:
        return "left"
    return "right"


def _curvature_offset(
    source_center: QPointF,
    destination_center: QPointF,
) -> float:
    direction_bias = -28.0 if source_center.x() <= destination_center.x() else 28.0
    return direction_bias


def _add_arrow_head(
    scene: QGraphicsScene,
    path: QPainterPath,
    color: QColor,
    move_key: str,
) -> QGraphicsPolygonItem:
    end = path.pointAtPercent(1.0)
    near_end = path.pointAtPercent(0.96)
    dx = end.x() - near_end.x()
    dy = end.y() - near_end.y()
    length = (dx**2 + dy**2) ** 0.5
    if length == 0:
        return

    ux = dx / length
    uy = dy / length
    arrow_size = 14.0

    left_point = QPointF(
        end.x() - (ux * arrow_size) - (uy * arrow_size * 0.6),
        end.y() - (uy * arrow_size) + (ux * arrow_size * 0.6),
    )
    right_point = QPointF(
        end.x() - (ux * arrow_size) + (uy * arrow_size * 0.6),
        end.y() - (uy * arrow_size) - (ux * arrow_size * 0.6),
    )

    polygon = QPolygonF([end, left_point, right_point])
    polygon_item = scene.addPolygon(polygon, QPen(color), QBrush(color))
    _set_item_focus_data(polygon_item, "move", move_key)
    return polygon_item


def _add_edge_label(
    scene: QGraphicsScene,
    label: str,
    path: QPainterPath,
    color: QColor,
    source_center: QPointF,
    move_key: str,
) -> QGraphicsSimpleTextItem:
    label_item = QGraphicsSimpleTextItem(label)
    label_item.setBrush(QBrush(color.darker(125)))
    bounds = label_item.boundingRect()
    anchor = path.pointAtPercent(0.28)
    if source_center.x() < path.pointAtPercent(1.0).x():
        x_position = anchor.x() - (bounds.width() * 0.15)
    else:
        x_position = anchor.x() - (bounds.width() * 0.85)
    label_item.setPos(x_position, anchor.y() - bounds.height() - 6.0)
    _set_item_focus_data(label_item, "move", move_key)
    scene.addItem(label_item)
    return label_item


def _apply_focus_state(
    position_items_by_key: dict[str, list[QGraphicsItem]],
    move_items_by_key: dict[str, list[QGraphicsItem]],
    positions_by_key: dict[str, Position],
    moves_by_key: dict[str, Move],
    selected_focus: tuple[str, str] | None,
    offer_hand_passthrough: bool,
) -> None:
    if selected_focus is None:
        return

    selection_kind, selection_key = selected_focus
    if selection_kind == "position" and selection_key in positions_by_key:
        selected_position = positions_by_key[selection_key]
        visible_outgoing_moves = [
            move
            for move in moves_by_key.values()
            if move.source is selected_position
        ]
        highlighted_position_keys = {
            selection_key,
            *(_position_option_key(move.destination) for move in visible_outgoing_moves),
        }
        highlighted_move_keys = {
            _move_option_key(move)
            for move in visible_outgoing_moves
        }
        if offer_hand_passthrough:
            passthrough_positions = [
                move.destination
                for move in visible_outgoing_moves
                if _is_same_side_move(move)
            ]
            passthrough_moves = [
                move
                for move in moves_by_key.values()
                if move.source in passthrough_positions
            ]
            highlighted_position_keys.update(
                _position_option_key(move.destination) for move in passthrough_moves
            )
            highlighted_move_keys.update(_move_option_key(move) for move in passthrough_moves)
    elif selection_kind == "move" and selection_key in moves_by_key:
        selected_move = moves_by_key[selection_key]
        highlighted_position_keys = {
            _position_option_key(selected_move.source),
            _position_option_key(selected_move.destination),
        }
        highlighted_move_keys = {selection_key}
    else:
        return

    for position_key, items in position_items_by_key.items():
        opacity = 1.0 if position_key in highlighted_position_keys else DIMMED_OPACITY
        for item in items:
            item.setOpacity(opacity)

    for move_key, items in move_items_by_key.items():
        opacity = 1.0 if move_key in highlighted_move_keys else DIMMED_OPACITY
        for item in items:
            item.setOpacity(opacity)


def _set_item_focus_data(item: QGraphicsItem, selection_kind: str, selection_key: str) -> None:
    item.setData(SELECTION_KIND_DATA_KEY, selection_kind)
    item.setData(SELECTION_ID_DATA_KEY, selection_key)


def _selection_for_item(item: QGraphicsItem | None) -> tuple[str, str] | None:
    current_item = item
    while current_item is not None:
        selection_kind = current_item.data(SELECTION_KIND_DATA_KEY)
        selection_key = current_item.data(SELECTION_ID_DATA_KEY)
        if selection_kind and selection_key:
            return str(selection_kind), str(selection_key)
        current_item = current_item.parentItem()
    return None


def _is_same_side_move(move: Move) -> bool:
    if move.source is move.destination:
        return False
    source_side = _position_side(move.source)
    destination_side = _position_side(move.destination)
    return source_side in {"left", "right"} and source_side == destination_side
