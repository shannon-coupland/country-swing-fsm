from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QAction, QBrush, QColor, QPainter, QPainterPath, QPen, QPolygonF, QTextOption, QTransform
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
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from country_swing_fsm.enums import Direction, MoveType, PositionType, Role
from country_swing_fsm.models import Move, Position


LEFT_COLOR = QColor("#16a34a")
RIGHT_COLOR = QColor("#f97316")
ACCENT_COLOR = QColor("#9333ea")
LEFT_FILL_COLOR = QColor("#dcfce7")
RIGHT_FILL_COLOR = QColor("#ffedd5")
ACCENT_FILL_COLOR = QColor("#f3e8ff")
BACKGROUND_COLOR = QColor("#f8fafc")
TOP_BAR_COLOR = QColor("#e2e8f0")
TEXT_COLOR = QColor("#0f172a")
LEAD_DIAGRAM_COLOR = QColor("#ec4899")
FOLLOW_DIAGRAM_COLOR = QColor("#2563eb")
DIAGRAM_LINE_COLOR = QColor("#334155")
DIAGRAM_LINE_OUTLINE_COLOR = QColor("#ffffff")

CIRCLE_DIAMETER = 120.0
LEFT_COLUMN_X = 120.0
MAIN_COLUMN_GAP = 700.0
RIGHT_COLUMN_X = LEFT_COLUMN_X + MAIN_COLUMN_GAP
ACCENT_START_X = 220.0
ACCENT_SPACING = 155.0
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
POSITION_ID_OFFSET = -18.0
POSITION_ID_TEXT_SIZE = 22.0
POSITION_LABEL_TEXT_SIZE = 12.0
MOVE_LABEL_TEXT_SIZE = 11.0
TWISTED_CONNECTION_CROSSBAR_WIDTH = 28.0

GROUP_ORDER = {
    (False, 1): 0,
    (False, 2): 1,
    (True, 1): 2,
    (True, 2): 3,
}
DIRECTION_ORDER = {
    Direction.LEFT: 0,
    Direction.RIGHT: 1,
}
class MainWindow(QMainWindow):
    def __init__(self, positions: list[Position], moves: list[Move]) -> None:
        super().__init__()
        self.all_positions = positions
        self.all_moves = moves
        self.position_button: QToolButton | None = None
        self.moves_button: QToolButton | None = None
        self.position_actions_by_key: dict[str, QAction] = {}
        self.move_type_actions_by_type: dict[MoveType, QAction] = {}
        self.show_all_positions_action: QAction | None = None
        self.show_no_positions_action: QAction | None = None
        self.show_all_moves_action: QAction | None = None
        self.show_no_moves_action: QAction | None = None
        self._position_menu: QMenu | None = None
        self.position_lookup_by_key: dict[str, Position] = {
            _position_option_key(position): position for position in self.all_positions
        }
        self.move_lookup_by_key: dict[str, Move] = {
            _move_option_key(move): move for move in self.all_moves
        }
        self.move_keys_by_type: dict[MoveType, set[str]] = {
            move_type: {
                move_key
                for move_key, move in self.move_lookup_by_key.items()
                if move.move_type == move_type
            }
            for move_type in MoveType
        }
        self.visible_position_keys: set[str] = set(self.position_lookup_by_key)
        self.visible_move_keys: set[str] = set(self.move_lookup_by_key)
        self.display_role = Role.LEAD
        self.offer_hand_passthrough = False
        self.show_incoming_moves = False
        self.selected_focus: tuple[str, str] | None = None
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

        left_container = QWidget()
        left_layout = QHBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        mode_container = QWidget()
        mode_layout = QHBoxLayout(mode_container)
        mode_layout.setContentsMargins(0, 0, 8, 0)
        mode_layout.setSpacing(6)
        lead_mode_label = QLabel("Lead View")
        lead_mode_label.setStyleSheet(
            f"color: {LEAD_DIAGRAM_COLOR.name()}; font-weight: 700;"
        )
        mode_layout.addWidget(lead_mode_label)
        mode_slider = ModeToggleSlider()
        mode_slider.setRange(0, 1)
        mode_slider.setValue(0)
        mode_slider.setFixedWidth(32)
        mode_slider.setSingleStep(1)
        mode_slider.setPageStep(1)
        mode_slider.setTickInterval(1)
        mode_slider.valueChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(mode_slider)
        follow_mode_label = QLabel("Follow View")
        follow_mode_label.setStyleSheet(
            f"color: {FOLLOW_DIAGRAM_COLOR.name()}; font-weight: 700;"
        )
        mode_layout.addWidget(follow_mode_label)
        left_layout.addWidget(mode_container)
        left_layout.addStretch(1)

        center_container = QWidget()
        center_layout = QHBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(8)
        self._add_position_selector_button(center_layout)
        self._add_move_selector_button(center_layout)

        right_container = QWidget()
        right_layout = QHBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        right_layout.addStretch(1)
        offer_hand_passthrough_checkbox = QCheckBox("Offer/Drop Hand Passthrough")
        offer_hand_passthrough_checkbox.toggled.connect(self._on_offer_hand_passthrough_toggled)
        right_layout.addWidget(offer_hand_passthrough_checkbox)
        show_incoming_moves_checkbox = QCheckBox("Show Incoming Moves")
        show_incoming_moves_checkbox.toggled.connect(self._on_show_incoming_moves_toggled)
        right_layout.addWidget(show_incoming_moves_checkbox)

        layout.addWidget(left_container, 1)
        layout.addWidget(center_container, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(right_container, 1)
        return bar

    def _add_position_selector_button(self, layout: QHBoxLayout) -> None:
        button = QToolButton()
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setAutoRaise(True)
        button.setStyleSheet(
            f"QToolButton {{ background-color: {TOP_BAR_COLOR.name()}; border: 1px solid #94a3b8; border-radius: 6px; padding: 4px 10px; color: {TEXT_COLOR.name()}; }}"
        )

        menu = PersistentFilterMenu(button)
        _add_menu_header(menu, "Visibility")
        self.show_all_positions_action = QAction("Show All", menu)
        self.show_all_positions_action.setCheckable(True)
        self.show_all_positions_action.triggered.connect(self._show_all_positions)
        menu.addAction(self.show_all_positions_action)
        self.show_no_positions_action = QAction("Show None", menu)
        self.show_no_positions_action.setCheckable(True)
        self.show_no_positions_action.triggered.connect(self._show_no_positions)
        menu.addAction(self.show_no_positions_action)

        for section_label, positions in self._position_sections():
            _add_menu_header(menu, section_label)
            for position in positions:
                position_key = _position_option_key(position)
                action = QAction(_position_menu_label(position, self.display_role), menu)
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

    def _add_move_selector_button(self, layout: QHBoxLayout) -> None:
        button = QToolButton()
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setAutoRaise(True)
        button.setStyleSheet(
            f"QToolButton {{ background-color: {TOP_BAR_COLOR.name()}; border: 1px solid #94a3b8; border-radius: 6px; padding: 4px 10px; color: {TEXT_COLOR.name()}; }}"
        )

        menu = PersistentFilterMenu(button)
        _add_menu_header(menu, "Visibility")
        self.show_all_moves_action = QAction("Show All", menu)
        self.show_all_moves_action.setCheckable(True)
        self.show_all_moves_action.triggered.connect(self._show_all_moves)
        menu.addAction(self.show_all_moves_action)
        self.show_no_moves_action = QAction("Show None", menu)
        self.show_no_moves_action.setCheckable(True)
        self.show_no_moves_action.triggered.connect(self._show_no_moves)
        menu.addAction(self.show_no_moves_action)

        _add_menu_header(menu, "Move Type")
        for move_type in MoveType:
            action = QAction(_move_type_menu_label(move_type), menu)
            action.setCheckable(True)
            action.setChecked(True)
            if not self.move_keys_by_type[move_type]:
                action.setEnabled(False)
            action.triggered.connect(
                lambda checked, move_type=move_type: self._on_move_type_visibility_toggled(
                    move_type,
                    checked,
                )
            )
            menu.addAction(action)
            self.move_type_actions_by_type[move_type] = action

        button.setMenu(menu)
        self.moves_button = button
        self._update_move_selector_label()
        layout.addWidget(button)

    def _position_sections(self) -> list[tuple[str, list[Position]]]:
        sorted_positions = self._sorted_position_selector_positions()
        return [
            (
                "Uncrossed",
                [
                    position
                    for position in sorted_positions
                    if not _is_accent_position(position) and not position.crossed
                ],
            ),
            (
                "Crossed",
                [
                    position
                    for position in sorted_positions
                    if not _is_accent_position(position) and position.crossed
                ],
            ),
            (
                "Accent",
                [position for position in sorted_positions if _is_accent_position(position)],
            ),
        ]

    def _on_position_visibility_toggled(self, position_key: str, checked: bool) -> None:
        if checked:
            self.visible_position_keys.add(position_key)
        else:
            self.visible_position_keys.discard(position_key)
        self._update_position_selector_label()
        if not self._suppress_refresh:
            self._refresh_scene(preserve_view=True)

    def _on_move_visibility_toggled(self, move_key: str, checked: bool) -> None:
        if checked:
            self.visible_move_keys.add(move_key)
        else:
            self.visible_move_keys.discard(move_key)
        self._update_move_selector_label()
        if not self._suppress_refresh:
            self._refresh_scene(preserve_view=True)

    def _on_move_type_visibility_toggled(self, move_type: MoveType, checked: bool) -> None:
        visible_move_types = {
            current_move_type
            for current_move_type, action in self.move_type_actions_by_type.items()
            if action.isChecked()
        }
        if checked:
            visible_move_types.add(move_type)
        else:
            visible_move_types.discard(move_type)

        self.visible_move_keys = {
            move_key
            for move_key, move in self.move_lookup_by_key.items()
            if move.move_type in visible_move_types
        }
        self._update_move_selector_label()
        self._refresh_scene(preserve_view=True)

    def _show_all_positions(self) -> None:
        self._suppress_refresh = True
        try:
            self.visible_position_keys = set(self.position_lookup_by_key)
            for action in self.position_actions_by_key.values():
                if not action.isChecked():
                    action.setChecked(True)
            self._update_position_selector_label()
        finally:
            self._suppress_refresh = False

        self._refresh_scene(preserve_view=True)

    def _show_no_positions(self) -> None:
        self._suppress_refresh = True
        try:
            self.visible_position_keys.clear()
            for action in self.position_actions_by_key.values():
                if action.isChecked():
                    action.setChecked(False)
            self._update_position_selector_label()
        finally:
            self._suppress_refresh = False

        self._refresh_scene(preserve_view=True)

    def _show_all_moves(self) -> None:
        self.visible_move_keys = set(self.move_lookup_by_key)
        self._sync_move_type_action_states()
        self._update_move_selector_label()
        self._refresh_scene(preserve_view=True)

    def _show_no_moves(self) -> None:
        self.visible_move_keys.clear()
        self._sync_move_type_action_states()
        self._update_move_selector_label()
        self._refresh_scene(preserve_view=True)

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
        if self.show_all_positions_action is not None:
            self.show_all_positions_action.setChecked(visible_count == total_count)
        if self.show_no_positions_action is not None:
            self.show_no_positions_action.setChecked(visible_count == 0)

    def _update_move_selector_label(self) -> None:
        if self.moves_button is None:
            return

        total_count = len(self.move_lookup_by_key)
        visible_count = len(self.visible_move_keys)
        if visible_count == total_count:
            label = "Moves"
        else:
            label = f"Moves ({visible_count})"
        self.moves_button.setText(label)
        if self.show_all_moves_action is not None:
            self.show_all_moves_action.setChecked(visible_count == total_count)
        if self.show_no_moves_action is not None:
            self.show_no_moves_action.setChecked(visible_count == 0)
        self._sync_move_type_action_states()

    def _on_mode_changed(self, value: int) -> None:
        self.display_role = Role.FOLLOW if value == 1 else Role.LEAD
        self._update_position_action_labels()
        self._refresh_scene(preserve_view=True)

    def _on_offer_hand_passthrough_toggled(self, checked: bool) -> None:
        self.offer_hand_passthrough = checked
        self._refresh_scene(preserve_view=True)

    def _on_show_incoming_moves_toggled(self, checked: bool) -> None:
        self.show_incoming_moves = checked
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
            and _move_option_key(move) in self.visible_move_keys
        ]
        self.view.load_scene(
            build_scene(
                visible_positions,
                visible_moves,
                display_role=self.display_role,
                selected_focus=self.selected_focus,
                offer_hand_passthrough=self.offer_hand_passthrough,
                show_incoming_moves=self.show_incoming_moves,
                on_focus_change=self._on_focus_change,
                on_position_menu_request=self._show_position_move_menu,
            ),
            preserve_view=preserve_view,
        )

    def _sorted_position_selector_positions(self) -> list[Position]:
        left_positions = _sorted_column_positions(
            [
                position
                for position in self.all_positions
                if (
                    not _is_accent_position(position)
                    and position.lead_start_step_foot == Direction.LEFT
                )
            ]
        )
        right_positions = _sorted_column_positions(
            [
                position
                for position in self.all_positions
                if (
                    not _is_accent_position(position)
                    and position.lead_start_step_foot == Direction.RIGHT
                )
            ]
        )
        accent_positions = _sorted_accent_positions(
            [position for position in self.all_positions if _is_accent_position(position)]
        )
        return [*left_positions, *right_positions, *accent_positions]

    def _on_focus_change(self, selected_focus: tuple[str, str] | None) -> None:
        if self.selected_focus == selected_focus:
            return
        self.selected_focus = selected_focus
        self._refresh_scene(preserve_view=True)

    def _show_position_move_menu(self, position_key: str, screen_pos: QPoint) -> None:
        position = self.position_lookup_by_key.get(position_key)
        if position is None:
            return

        menu = PersistentFilterMenu(self)
        self._position_menu = menu
        _add_menu_header(menu, _position_menu_label(position, self.display_role))
        if not position.outgoing_moves:
            empty_action = QAction("(No outgoing moves)", menu)
            empty_action.setEnabled(False)
            menu.addAction(empty_action)
        else:
            for outgoing_move in position.outgoing_moves:
                move = outgoing_move.outgoing_move
                move_key = _move_option_key(move)
                action = QAction(_move_menu_label(move), menu)
                action.setCheckable(True)
                action.setChecked(move_key in self.visible_move_keys)
                action.toggled.connect(
                    lambda checked, move_key=move_key: self._on_move_visibility_toggled(
                        move_key,
                        checked,
                    )
                )
                menu.addAction(action)
        menu.exec(screen_pos)
        self._position_menu = None

    def _update_position_action_labels(self) -> None:
        for position_key, action in self.position_actions_by_key.items():
            action.setText(
                _position_menu_label(
                    self.position_lookup_by_key[position_key],
                    self.display_role,
                )
            )

    def _sync_move_type_action_states(self) -> None:
        for move_type, action in self.move_type_actions_by_type.items():
            move_keys = self.move_keys_by_type[move_type]
            if not move_keys:
                action.setChecked(False)
                continue
            action.setChecked(move_keys.issubset(self.visible_move_keys))


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


def _add_menu_header(menu: QMenu, label: str) -> QLabel:
    container = QWidget(menu)
    layout = QVBoxLayout(container)
    layout.setContentsMargins(10, 8, 10, 4)
    layout.setSpacing(0)

    header = QLabel(label, container)
    header.setStyleSheet(
        f"color: {TEXT_COLOR.name()}; font-weight: 700; font-size: 11px;"
    )
    layout.addWidget(header)

    action = QWidgetAction(menu)
    action.setDefaultWidget(container)
    menu.addAction(action)
    return header


class InteractiveScene(QGraphicsScene):
    def __init__(
        self,
        on_focus_change: Callable[[tuple[str, str] | None], None] | None = None,
        on_position_menu_request: Callable[[str, QPoint], None] | None = None,
    ) -> None:
        super().__init__()
        self._on_focus_change = on_focus_change
        self._on_position_menu_request = on_position_menu_request

    def mousePressEvent(self, event) -> None:
        clicked_item = self.itemAt(event.scenePos(), QTransform())
        selection = _selection_for_item(clicked_item)
        if (
            selection is not None
            and selection[0] == "position"
            and self._on_position_menu_request is not None
            and event.button() == Qt.MouseButton.RightButton
        ):
            self._on_position_menu_request(selection[1], event.screenPos())
            event.accept()
            return
        if self._on_focus_change is not None and event.button() == Qt.MouseButton.LeftButton:
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
    show_incoming_moves: bool = False,
    on_focus_change: Callable[[tuple[str, str] | None], None] | None = None,
    on_position_menu_request: Callable[[str, QPoint], None] | None = None,
) -> QGraphicsScene:
    scene = InteractiveScene(
        on_focus_change=on_focus_change,
        on_position_menu_request=on_position_menu_request,
    )
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
                not _is_accent_position(position)
                and position.lead_start_step_foot == Direction.LEFT
            )
        ]
    )
    right_positions = _sorted_column_positions(
        [
            position
            for position in positions
            if (
                not _is_accent_position(position)
                and position.lead_start_step_foot == Direction.RIGHT
            )
        ]
    )
    accent_positions = _sorted_accent_positions(
        [position for position in positions if _is_accent_position(position)]
    )
    accent_row_width = (max(len(accent_positions) - 1, 0)) * ACCENT_SPACING
    right_column_x = max(
        RIGHT_COLUMN_X,
        (2.5 * ACCENT_START_X) + accent_row_width - LEFT_COLUMN_X,
    )

    centers_by_position_id: dict[int, QPointF] = {}
    position_items_by_key: dict[str, list[QGraphicsItem]] = {}
    move_items_by_key: dict[str, list[QGraphicsItem]] = {}


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

    accent_row_start_x = ((LEFT_COLUMN_X + right_column_x) / 2.0) - (accent_row_width / 2.0)
    accent_row_y = max(
        left_y_positions[-1] if left_y_positions else 0.0,
        right_y_positions[-1] if right_y_positions else 0.0,
    ) + ROW_SPACING

    for index, position in enumerate(accent_positions):
        center = QPointF(accent_row_start_x + (index * ACCENT_SPACING), accent_row_y)
        centers_by_position_id[id(position)] = center
        position_key = _position_option_key(position)
        position_items_by_key[position_key] = _add_position_node(
            scene,
            position,
            center,
            ACCENT_COLOR,
            display_role,
            position_key,
        )

    parallel_move_groups: dict[tuple[int, int], list[Move]] = {}
    for move in filtered_moves:
        key = (id(move.source), id(move.destination))
        parallel_move_groups.setdefault(key, []).append(move)

    for sibling_moves in parallel_move_groups.values():
        move = sibling_moves[0]
        move_key = _move_group_key(move)
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
        moves_by_key={_move_group_key(move): move for move in filtered_moves},
        selected_focus=selected_focus,
        offer_hand_passthrough=offer_hand_passthrough,
        show_incoming_moves=show_incoming_moves,
    )

    scene.setSceneRect(scene.itemsBoundingRect().adjusted(-80.0, -60.0, 80.0, 60.0))
    return scene


def _sorted_column_positions(positions: list[Position]) -> list[Position]:
    return sorted(positions, key=lambda position: position.position_id)


def _sorted_accent_positions(positions: list[Position]) -> list[Position]:
    return sorted(positions, key=lambda position: position.position_id)


def _is_accent_position(position: Position) -> bool:
    return position.position_type in {PositionType.ACCENT_DIP, PositionType.ACCENT_OTHER}


def _hands_joined_sort_key(position: Position) -> tuple[int, ...]:
    return tuple(
        DIRECTION_ORDER[direction]
        for direction in position.sub_position_for_role(Role.LEAD).hands_joined
    )


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
    circle.setBrush(QBrush(_position_fill_color(position)))
    circle.setPen(QPen(outline_color, OUTER_CIRCLE_PEN_WIDTH))
    _set_item_focus_data(circle, "position", position_key)
    scene.addItem(circle)

    items: list[QGraphicsItem] = [circle]
    items.append(_add_position_id_label(scene, position, center, outline_color, position_key))
    if position.position_type == PositionType.OPEN or position.label is None:
        items.extend(_add_position_diagram(scene, position, center, display_role, position_key))
        return items

    label = _display_position_label(position, display_role)
    text_item = QGraphicsTextItem(label)
    text_item.setDefaultTextColor(outline_color)
    text_item.setTextWidth(CIRCLE_DIAMETER - 20.0)
    text_item.document().setDocumentMargin(0.0)
    text_option = text_item.document().defaultTextOption()
    text_option.setAlignment(Qt.AlignmentFlag.AlignCenter)
    text_item.document().setDefaultTextOption(text_option)
    font = text_item.font()
    font.setPointSizeF(POSITION_LABEL_TEXT_SIZE)
    font.setBold(True)
    text_item.setFont(font)
    bounds = text_item.boundingRect()
    text_item.setPos(center.x() - (bounds.width() / 2.0), center.y() - (bounds.height() / 2.0))
    _set_item_focus_data(text_item, "position", position_key)
    scene.addItem(text_item)
    items.append(text_item)
    return items


def _add_position_diagram(
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

    if position.position_type == PositionType.TWISTED and position.label is None and hand_count == 2:
        items = _add_standard_hand_connection_items(
            scene,
            position,
            centers_by_role,
            display_role,
            position_key,
        )
        items.extend(_add_twisted_crossbar_items(scene, centers_by_role, position_key))
        return items

    return _add_standard_hand_connection_items(
        scene,
        position,
        centers_by_role,
        display_role,
        position_key,
    )


def _add_standard_hand_connection_items(
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


def _add_twisted_crossbar_items(
    scene: QGraphicsScene,
    centers_by_role: dict[Role, QPointF],
    position_key: str,
) -> list[QGraphicsItem]:
    swirl_center = QPointF(
        (centers_by_role[Role.LEAD].x() + centers_by_role[Role.FOLLOW].x()) / 2.0,
        (centers_by_role[Role.LEAD].y() + centers_by_role[Role.FOLLOW].y()) / 2.0,
    )
    outline_pen = QPen(DIAGRAM_LINE_OUTLINE_COLOR, CONNECTION_OUTLINE_PEN_WIDTH)
    pen = QPen(DIAGRAM_LINE_COLOR, CONNECTION_PEN_WIDTH)
    start = QPointF(
        swirl_center.x() - (TWISTED_CONNECTION_CROSSBAR_WIDTH / 2.0),
        swirl_center.y(),
    )
    end = QPointF(
        swirl_center.x() + (TWISTED_CONNECTION_CROSSBAR_WIDTH / 2.0),
        swirl_center.y(),
    )
    outline_item = scene.addLine(
        start.x(),
        start.y(),
        end.x(),
        end.y(),
        outline_pen,
    )
    _set_item_focus_data(outline_item, "position", position_key)
    line_item = scene.addLine(
        start.x(),
        start.y(),
        end.x(),
        end.y(),
        pen,
    )
    _set_item_focus_data(line_item, "position", position_key)
    return [outline_item, line_item]


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
    text_item.setBrush(QBrush(Qt.GlobalColor.white))
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
    if position.label:
        return position.label
    return _generated_position_label(position, display_role)


def _generated_position_label(position: Position, display_role: Role) -> str:
    sub_position = position.sub_position_for_role(display_role)
    step_label = f"{sub_position.start_step_foot.value.title()} Step"
    hands_label = _generated_hands_label(sub_position.hands_joined)
    if not sub_position.hands_joined:
        label = f"{step_label} {hands_label}"
    else:
        crossed_label = "Crossed" if position.crossed else "Uncrossed"
        label = f"{step_label} {crossed_label} {hands_label}"

    if position.position_type == PositionType.TWISTED:
        return f"{label} Twisted"
    return label


def _generated_hands_label(hands_joined: list[Direction]) -> str:
    if len(hands_joined) == 2:
        return "Both Hands"
    if len(hands_joined) == 1:
        return f"{hands_joined[0].value.title()} Hand"
    return "No Hands"


def _position_menu_label(position: Position, display_role: Role) -> str:
    return f"{position.position_id} - {_display_position_label(position, display_role)}"


def _move_menu_label(move: Move) -> str:
    return move.label or "(unlabeled)"


def _move_type_menu_label(move_type: MoveType) -> str:
    if move_type == MoveType.OFFER_OR_DROP:
        return "Offer/Drop"
    return move_type.value.replace("_", " ").title()


def _add_position_id_label(
    scene: QGraphicsScene,
    position: Position,
    center: QPointF,
    color: QColor,
    position_key: str,
) -> QGraphicsSimpleTextItem:
    text_item = QGraphicsSimpleTextItem(str(position.position_id))
    text_item.setBrush(QBrush(color))
    font = text_item.font()
    font.setBold(True)
    font.setPointSizeF(POSITION_ID_TEXT_SIZE)
    text_item.setFont(font)
    bounds = text_item.boundingRect()
    radius = CIRCLE_DIAMETER / 2.0

    side = _position_side(position)
    if side in {"left", "accent"}:
        x_position = center.x() - radius - bounds.width() - POSITION_ID_OFFSET
    else:
        x_position = center.x() + radius + POSITION_ID_OFFSET

    y_position = center.y() - radius - bounds.height() - POSITION_ID_OFFSET
    text_item.setPos(x_position, y_position)
    _set_item_focus_data(text_item, "position", position_key)
    scene.addItem(text_item)
    return text_item


def _position_option_key(position: Position) -> str:
    return f"position:{id(position)}"


def _move_option_key(move: Move) -> str:
    return f"move:{id(move)}"


def _move_group_key(move: Move) -> str:
    return f"move-group:{id(move.source)}:{id(move.destination)}"


def _position_fill_color(position: Position) -> QColor:
    side = _position_side(position)
    if side == "left":
        return LEFT_FILL_COLOR
    if side == "right":
        return RIGHT_FILL_COLOR
    return ACCENT_FILL_COLOR


def _add_move_edge(
    scene: QGraphicsScene,
    move: Move,
    source_center: QPointF,
    destination_center: QPointF,
    label: str,
    move_key: str,
) -> list[QGraphicsItem]:
    if _is_accent_position(move.source):
        color = ACCENT_COLOR
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
        ("left", "accent"): ("top_right", "top_left", "right", "right"),
        ("right", "left"): ("bottom_left", "bottom_right", "left", "left"),
        ("right", "right"): ("top_right", "bottom_right", "right", "left"),
        ("right", "accent"): ("bottom_left", "top_right", "left", "left"),
        ("accent", "left"): ("top_left", "bottom_right", "left", "left"),
        ("accent", "right"): ("top_right", "top_left", "right", "right"),
    }
    return routing_table.get(
        (source_side, destination_side),
        ("top_right", "top_left", "right", "right"),
    )


def _position_side(position: Position) -> str:
    if _is_accent_position(position):
        return "accent"
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
    font = label_item.font()
    font.setPointSizeF(MOVE_LABEL_TEXT_SIZE)
    label_item.setFont(font)
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
    show_incoming_moves: bool,
) -> None:
    if selected_focus is None:
        return

    selection_kind, selection_key = selected_focus
    if selection_kind == "position" and selection_key in positions_by_key:
        selected_position_key = selection_key
        selected_position = positions_by_key[selection_key]
        visible_outgoing_moves = [
            move
            for move in moves_by_key.values()
            if move.source is selected_position
        ]
        directly_highlighted_moves = [
            move
            for move in visible_outgoing_moves
            if offer_hand_passthrough or move.move_type != MoveType.OFFER_OR_DROP
        ]
        highlighted_position_keys = {
            selection_key,
            *(_position_option_key(move.destination) for move in directly_highlighted_moves),
        }
        highlighted_move_keys = {
            _move_group_key(move)
            for move in directly_highlighted_moves
        }
        if offer_hand_passthrough:
            passthrough_positions = [
                move.destination
                for move in visible_outgoing_moves
                if move.move_type == MoveType.OFFER_OR_DROP
            ]
            passthrough_moves = [
                move
                for move in moves_by_key.values()
                if move.source in passthrough_positions
            ]
            highlighted_position_keys.update(
                _position_option_key(move.destination) for move in passthrough_moves
            )
            highlighted_move_keys.update(_move_group_key(move) for move in passthrough_moves)
        if show_incoming_moves:
            visible_incoming_moves = [
                move
                for move in moves_by_key.values()
                if move.destination is selected_position
                and (offer_hand_passthrough or move.move_type != MoveType.OFFER_OR_DROP)
            ]
            highlighted_position_keys.update(
                _position_option_key(move.source) for move in visible_incoming_moves
            )
            highlighted_move_keys.update(_move_group_key(move) for move in visible_incoming_moves)
            if offer_hand_passthrough:
                direct_incoming_source_ids = {
                    id(incoming_move.source) for incoming_move in visible_incoming_moves
                }
                passthrough_incoming_moves = [
                    move
                    for move in moves_by_key.values()
                    if (
                        id(move.destination) in direct_incoming_source_ids
                        and move.move_type == MoveType.OFFER_OR_DROP
                    )
                ]
                highlighted_position_keys.update(
                    _position_option_key(move.source) for move in passthrough_incoming_moves
                )
                highlighted_move_keys.update(
                    _move_group_key(move) for move in passthrough_incoming_moves
                )
    elif selection_kind == "move" and selection_key in moves_by_key:
        selected_position_key = None
        selected_move = moves_by_key[selection_key]
        highlighted_position_keys = {
            _position_option_key(selected_move.source),
            _position_option_key(selected_move.destination),
        }
        highlighted_move_keys = {selection_key}
    else:
        return

    for position_key, items in position_items_by_key.items():
        if items and isinstance(items[0], QGraphicsEllipseItem):
            fill_color = _position_fill_color(positions_by_key[position_key])
            if position_key == selected_position_key:
                fill_color = fill_color.darker(112)
            items[0].setBrush(QBrush(fill_color))
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

