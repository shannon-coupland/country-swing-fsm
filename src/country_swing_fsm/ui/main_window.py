from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QAction, QBrush, QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from country_swing_fsm.enums import Direction, PositionType, Role
from country_swing_fsm.models import Move, Position
from country_swing_fsm.ui.filtering import FilterOption, FilterOptions, build_filter_options, filter_graph


LEFT_COLOR = QColor("#2563eb")
RIGHT_COLOR = QColor("#f97316")
LEFT_TWISTED_COLOR = QColor("#60a5fa")
RIGHT_TWISTED_COLOR = QColor("#fdba74")
IMPACT_COLOR = QColor("#9333ea")
BACKGROUND_COLOR = QColor("#f8fafc")
TOP_BAR_COLOR = QColor("#e2e8f0")

CIRCLE_DIAMETER = 120.0
LEFT_COLUMN_X = 120.0
RIGHT_COLUMN_X = 680.0
IMPACT_START_X = 220.0
IMPACT_SPACING = 180.0
TOP_MARGIN = 80.0
ROW_SPACING = 220.0
GROUPED_ROW_SPACING = max(ROW_SPACING / 3.0, CIRCLE_DIAMETER + 24.0)

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
    "positions": "Positions",
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
            "positions": set(),
            "lead_moves": set(),
            "follow_moves": set(),
        }
        self.filter_buttons: dict[str, QToolButton] = {}
        self.filter_actions: dict[str, list[QAction]] = {}
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

        self._add_filter_button(
            layout,
            "positions",
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
        return bar

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

    def _clear_all_filters(self) -> None:
        self._suppress_refresh = True
        try:
            for filter_key, selected_keys in self.selected_filter_keys.items():
                selected_keys.clear()
                for action in self.filter_actions[filter_key]:
                    if action.isChecked():
                        action.setChecked(False)
                self._update_filter_button_label(filter_key)
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

    def _refresh_scene(self) -> None:
        filtered_graph = filter_graph(
            all_positions=self.all_positions,
            all_moves=self.all_moves,
            position_options=self.filter_options.position_options,
            selected_position_keys=self.selected_filter_keys["positions"],
            lead_move_options=self.filter_options.lead_move_options,
            selected_lead_move_keys=self.selected_filter_keys["lead_moves"],
            follow_move_options=self.filter_options.follow_move_options,
            selected_follow_move_keys=self.selected_filter_keys["follow_moves"],
        )
        self.view.load_scene(build_scene(filtered_graph.positions, filtered_graph.moves))


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

    def load_scene(self, scene: QGraphicsScene) -> None:
        self._has_manual_zoom = False
        self.setScene(scene)
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


def build_scene(positions: list[Position], moves: list[Move]) -> QGraphicsScene:
    scene = QGraphicsScene()
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

    _add_column_header(scene, "Lead starts LEFT", LEFT_COLUMN_X, LEFT_COLOR)
    _add_column_header(scene, "Lead starts RIGHT", right_column_x, RIGHT_COLOR)

    left_y_positions, right_y_positions = _aligned_column_y_positions(
        left_positions,
        right_positions,
    )

    for index, position in enumerate(left_positions):
        center = QPointF(LEFT_COLUMN_X, left_y_positions[index])
        centers_by_position_id[id(position)] = center
        _add_position_node(
            scene,
            position,
            center,
            _position_color(position, LEFT_COLOR, LEFT_TWISTED_COLOR),
        )

    for index, position in enumerate(right_positions):
        center = QPointF(right_column_x, right_y_positions[index])
        centers_by_position_id[id(position)] = center
        _add_position_node(
            scene,
            position,
            center,
            _position_color(position, RIGHT_COLOR, RIGHT_TWISTED_COLOR),
        )

    impact_row_start_x = ((LEFT_COLUMN_X + right_column_x) / 2.0) - (impact_row_width / 2.0)
    impact_row_y = max(
        left_y_positions[-1] if left_y_positions else 0.0,
        right_y_positions[-1] if right_y_positions else 0.0,
    ) + ROW_SPACING

    for index, position in enumerate(impact_positions):
        center = QPointF(impact_row_start_x + (index * IMPACT_SPACING), impact_row_y)
        centers_by_position_id[id(position)] = center
        _add_position_node(scene, position, center, IMPACT_COLOR)

    parallel_move_groups: dict[tuple[int, int], list[Move]] = {}
    for move in filtered_moves:
        key = (id(move.source), id(move.destination))
        parallel_move_groups.setdefault(key, []).append(move)

    for sibling_moves in parallel_move_groups.values():
        move = sibling_moves[0]
        _add_move_edge(
            scene=scene,
            move=move,
            source_center=centers_by_position_id[id(move.source)],
            destination_center=centers_by_position_id[id(move.destination)],
            label="\n".join(sibling_move.label or "(unlabeled)" for sibling_move in sibling_moves),
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
    color: QColor,
) -> None:
    circle_rect = QRectF(
        center.x() - (CIRCLE_DIAMETER / 2.0),
        center.y() - (CIRCLE_DIAMETER / 2.0),
        CIRCLE_DIAMETER,
        CIRCLE_DIAMETER,
    )
    circle = QGraphicsEllipseItem(circle_rect)
    circle.setBrush(QBrush(color))
    circle.setPen(QPen(color.darker(120), 2))
    scene.addItem(circle)

    label = position.label or "(unlabeled)"
    text_item = QGraphicsTextItem(label)
    text_item.setDefaultTextColor(Qt.GlobalColor.white)
    text_item.setTextWidth(CIRCLE_DIAMETER - 20.0)
    text_item.document().setDocumentMargin(0.0)
    bounds = text_item.boundingRect()
    text_item.setPos(center.x() - (bounds.width() / 2.0), center.y() - (bounds.height() / 2.0))
    scene.addItem(text_item)


def _position_color(position: Position, base_color: QColor, twisted_color: QColor) -> QColor:
    if position.position_type == PositionType.TWISTED:
        return twisted_color
    return base_color


def _add_move_edge(
    scene: QGraphicsScene,
    move: Move,
    source_center: QPointF,
    destination_center: QPointF,
    label: str,
) -> None:
    if move.source.position_type == PositionType.IMPACT:
        color = IMPACT_COLOR
    else:
        color = LEFT_COLOR if move.source.lead_start_step_foot == Direction.LEFT else RIGHT_COLOR
    pen = QPen(color, 3)

    start = _source_circle_edge_point(move.source, source_center)
    end = _destination_circle_edge_point(move.destination, destination_center)
    path = _build_edge_path(
        start=start,
        end=end,
        curvature_offset=_curvature_offset(
            source_center=source_center,
            destination_center=destination_center,
        ),
    )

    path_item = QGraphicsPathItem(path)
    path_item.setPen(pen)
    scene.addItem(path_item)

    _add_arrow_head(scene, path, color)
    _add_edge_label(scene, label, path, color, source_center)


def _source_circle_edge_point(position: Position, center: QPointF) -> QPointF:
    radius = CIRCLE_DIAMETER / 2.0
    horizontal_offset = (3.0**0.5 / 2.0) * radius
    vertical_offset = 0.5 * radius

    if position.lead_start_step_foot == Direction.LEFT:
        return QPointF(center.x() + horizontal_offset, center.y() - vertical_offset)

    return QPointF(center.x() - horizontal_offset, center.y() + vertical_offset)


def _destination_circle_edge_point(position: Position, center: QPointF) -> QPointF:
    radius = CIRCLE_DIAMETER / 2.0
    horizontal_offset = (3.0**0.5 / 2.0) * radius
    vertical_offset = 0.5 * radius

    if position.lead_start_step_foot == Direction.LEFT:
        return QPointF(center.x() + horizontal_offset, center.y() + vertical_offset)

    return QPointF(center.x() - horizontal_offset, center.y() - vertical_offset)


def _build_edge_path(start: QPointF, end: QPointF, curvature_offset: float) -> QPainterPath:
    path = QPainterPath(start)
    control_offset = max(abs(end.x() - start.x()) * 0.25, 70.0)
    direction = 1.0 if end.x() >= start.x() else -1.0
    control_one = QPointF(
        start.x() + (control_offset * direction),
        start.y() + curvature_offset,
    )
    control_two = QPointF(
        end.x() - (control_offset * direction),
        end.y() + curvature_offset,
    )
    path.cubicTo(control_one, control_two, end)
    return path


def _curvature_offset(
    source_center: QPointF,
    destination_center: QPointF,
) -> float:
    direction_bias = -28.0 if source_center.x() <= destination_center.x() else 28.0
    return direction_bias


def _add_arrow_head(scene: QGraphicsScene, path: QPainterPath, color: QColor) -> None:
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
    scene.addPolygon(polygon, QPen(color), QBrush(color))


def _add_edge_label(
    scene: QGraphicsScene,
    label: str,
    path: QPainterPath,
    color: QColor,
    source_center: QPointF,
) -> None:
    label_item = QGraphicsSimpleTextItem(label)
    label_item.setBrush(QBrush(color.darker(125)))
    bounds = label_item.boundingRect()
    anchor = path.pointAtPercent(0.28)
    if source_center.x() < path.pointAtPercent(1.0).x():
        x_position = anchor.x() - (bounds.width() * 0.15)
    else:
        x_position = anchor.x() - (bounds.width() * 0.85)
    label_item.setPos(x_position, anchor.y() - bounds.height() - 6.0)
    scene.addItem(label_item)
