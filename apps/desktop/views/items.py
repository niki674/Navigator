from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsScene, QGraphicsTextItem

from packages.core.models import MapPoint, PointType


class MovableTextItem(QGraphicsTextItem):

    def __init__(self, text: str, parent_point_item):
        super().__init__(text)
        self.parent_point_item = parent_point_item
        self.setFlags(QGraphicsItem.ItemIgnoresTransformations)
        self.setDefaultTextColor(Qt.black)


class GraphicsPointItem(QGraphicsItem):

    def __init__(
        self,
        point: MapPoint,
        scene: QGraphicsScene,
        is_highlighted: bool = False,
    ):
        super().__init__()
        self.point = point
        self.scene_ref = scene
        self.is_highlighted = is_highlighted
        self.radius = 8.0

        self.setFlags(QGraphicsItem.ItemIgnoresTransformations)
        self.setPos(self.point.coords)

        self.text_item = None
        if self.point.point_type != PointType.REGULAR:
            display_text = self.point.name
            if self.point.alias:
                display_text += f"\n({self.point.alias})"

            self.text_item = MovableTextItem(display_text, self)
            font = QFont("Arial", self.point.font_size, QFont.Bold)
            self.text_item.setFont(font)
            self.scene_ref.addItem(self.text_item)
            self.update_text_position()

    def update_text_position(self):
        if self.text_item:
            rect = self.text_item.boundingRect()
            target_center = self.pos() + self.point.label_offset
            top_left = target_center - QPointF(rect.width() / 2.0, rect.height() / 2.0)
            self.text_item.setPos(top_left)

    def boundingRect(self) -> QRectF:
        # Не занимаем место в области отрисовки для служебных узлов коридоров
        if self.point.point_type == PointType.REGULAR:
            return QRectF()
        r = self.radius + 4.0
        return QRectF(-r, -r, 2.0 * r, 2.0 * r)

    def paint(self, painter: QPainter, option, widget=None):
        # Не рисуем видимую точку для узлов коридоров
        if self.point.point_type == PointType.REGULAR:
            return

        painter.setRenderHint(QPainter.Antialiasing)

        if self.is_highlighted:
            brush_color = QColor(0, 120, 255)
            pen_color = QColor(255, 255, 0)
            pen_width = 3.0
        elif self.point.is_favorite:
            brush_color = QColor(255, 215, 0)
            pen_color = Qt.black
            pen_width = 1.5
        elif self.point.point_type == PointType.STAIR:
            brush_color = QColor(255, 140, 0)
            pen_color = Qt.black
            pen_width = 1.5
        elif self.point.point_type == PointType.ROOM:
            brush_color = QColor(46, 139, 87)
            pen_color = Qt.black
            pen_width = 1.5
        else:
            brush_color = QColor(70, 130, 180)
            pen_color = Qt.black
            pen_width = 1.5

        painter.setBrush(brush_color)
        painter.setPen(QPen(pen_color, pen_width))
        painter.drawEllipse(QPointF(0.0, 0.0), self.radius, self.radius)