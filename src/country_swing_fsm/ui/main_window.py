from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsTextItem,
    QGraphicsView,
    QMainWindow,
)

from country_swing_fsm.enums import Direction
from country_swing_fsm.models import Move, Position


LEFT_COLOR = QColor("#2563eb")
RIGHT_COLOR = QColor("#f97316")
BACKGROUND_COLOR = QColor("#f8fafc")
TEXT_COLOR = QColor("#0f172a")

CIRCLE_DIAMETER = 120.0
LEFT_COLUMN_X = 120.0
RIGHT_COLUMN_X = 680.0
TOP_MARGIN = 80.0
ROW_SPACING = 220.0


class MainWindow(QMainWindow):
    def __init__(self, positions: list[Position], moves: list[Move]) -> None:
        super().__init__()
        self.positions = positions
        self.moves = moves

        self.setWindowTitle("Country Swing FSM")
        self.resize(1000, 700)

        self.scene = build_scene(positions, moves)
        self.view = DiagramView(self.scene)
        self.setCentralWidget(self.view)


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

    def _fit_scene(self) -> None:
        rect = self.sceneRect()
        if rect.isValid() and not rect.isEmpty():
            self.resetTransform()
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)


def build_scene(positions: list[Position], moves: list[Move]) -> QGraphicsScene:
    scene = QGraphicsScene()
    scene.setBackgroundBrush(BACKGROUND_COLOR)

    left_positions = [
        position for position in positions if position.lead_start_step_foot == Direction.LEFT
    ]
    right_positions = [
        position for position in positions if position.lead_start_step_foot == Direction.RIGHT
    ]

    centers_by_position_id: dict[int, QPointF] = {}

    _add_column_header(scene, "Lead starts LEFT", LEFT_COLUMN_X, LEFT_COLOR)
    _add_column_header(scene, "Lead starts RIGHT", RIGHT_COLUMN_X, RIGHT_COLOR)

    for index, position in enumerate(left_positions):
        center = QPointF(LEFT_COLUMN_X, TOP_MARGIN + 80.0 + (index * ROW_SPACING))
        centers_by_position_id[id(position)] = center
        _add_position_node(scene, position, center, LEFT_COLOR)

    for index, position in enumerate(right_positions):
        center = QPointF(RIGHT_COLUMN_X, TOP_MARGIN + 80.0 + (index * ROW_SPACING))
        centers_by_position_id[id(position)] = center
        _add_position_node(scene, position, center, RIGHT_COLOR)

    parallel_move_groups: dict[tuple[int, int], list[Move]] = {}
    for move in moves:
        key = (id(move.source), id(move.destination))
        parallel_move_groups.setdefault(key, []).append(move)

    for move in moves:
        sibling_moves = parallel_move_groups[(id(move.source), id(move.destination))]
        _add_move_edge(
            scene=scene,
            move=move,
            source_center=centers_by_position_id[id(move.source)],
            destination_center=centers_by_position_id[id(move.destination)],
            sibling_index=sibling_moves.index(move),
            sibling_count=len(sibling_moves),
        )

    scene.setSceneRect(scene.itemsBoundingRect().adjusted(-80.0, -60.0, 80.0, 60.0))
    return scene


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


def _add_move_edge(
    scene: QGraphicsScene,
    move: Move,
    source_center: QPointF,
    destination_center: QPointF,
    sibling_index: int,
    sibling_count: int,
) -> None:
    color = LEFT_COLOR if move.source.lead_start_step_foot == Direction.LEFT else RIGHT_COLOR
    pen = QPen(color, 3)

    start = _source_circle_edge_point(move.source, source_center)
    end = _destination_circle_edge_point(move.destination, destination_center)
    path = _build_edge_path(
        start=start,
        end=end,
        curvature_offset=_curvature_offset(
            sibling_index=sibling_index,
            sibling_count=sibling_count,
            source_center=source_center,
            destination_center=destination_center,
        ),
    )

    path_item = QGraphicsPathItem(path)
    path_item.setPen(pen)
    scene.addItem(path_item)

    _add_arrow_head(scene, path, color)
    _add_edge_label(scene, move.label or "(unlabeled)", path, color, source_center)


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
    sibling_index: int,
    sibling_count: int,
    source_center: QPointF,
    destination_center: QPointF,
) -> float:
    direction_bias = -28.0 if source_center.x() <= destination_center.x() else 28.0
    if sibling_count <= 1:
        return direction_bias

    spacing = 42.0
    center = (sibling_count - 1) / 2.0
    return direction_bias + ((sibling_index - center) * spacing)


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
