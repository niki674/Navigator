import json
import os
import sys
from enum import Enum

from PyQt5.QtCore import QLineF, QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

# --- 1. ТИПЫ ТОЧЕК И КЛАССЫ МОДЕЛИ ---
class PointType(Enum):
    ROOM = "room"
    STAIR = "stair"
    CORRIDOR_NODE = "corridor_node"


class MapPoint:
    def __init__(
        self,
        id: int,
        name: str,
        floor: int,
        coords: tuple[float, float],
        point_type: PointType = PointType.ROOM,
        alias: str = "",
        is_favorite: bool = False,
    ):
        self.id = id
        self.name = name
        self.floor = floor
        self.coords = coords  # (x, y)
        self.point_type = point_type
        self.alias = alias
        self.is_favorite = is_favorite

        # Дополнительные свойства оформления для GUI редактора
        self.label_offset = (0.0, 0.0)
        self.font_size = 10

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "floor": self.floor,
            "coords": [self.coords[0], self.coords[1]],
            "point_type": self.point_type.value,
            "alias": self.alias,
            "is_favorite": self.is_favorite,
            "label_offset": [self.label_offset[0], self.label_offset[1]],
            "font_size": self.font_size,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MapPoint":
        raw_type = d.get("point_type", "room")
        try:
            p_type = PointType(raw_type)
        except ValueError:
            p_type = PointType.ROOM

        # Обработка координат для обратной совместимости
        if "coords" in d:
            coords = tuple(d["coords"])
        elif "x" in d and "y" in d:
            coords = (float(d["x"]), float(d["y"]))
        else:
            coords = (0.0, 0.0)

        pt = cls(
            id=d["id"],
            name=d.get("name", ""),
            floor=d.get("floor", 1),
            coords=coords,
            point_type=p_type,
            alias=d.get("alias", ""),
            is_favorite=d.get("is_favorite", False),
        )

        offset = d.get("label_offset", [0.0, 0.0])
        pt.label_offset = (offset[0], offset[1])
        pt.font_size = d.get("font_size", 10)
        return pt


class CorridorSegment:
    """Отрезок коридора между двумя узловыми точками."""

    def __init__(self, id: int, floor: int, start_node_id: int, end_node_id: int):
        self.id = id
        self.floor = floor
        self.start_node_id = start_node_id
        self.end_node_id = end_node_id

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "floor": self.floor,
            "start_node_id": self.start_node_id,
            "end_node_id": self.end_node_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CorridorSegment":
        return cls(
            id=d["id"],
            floor=d["floor"],
            start_node_id=d["start_node_id"],
            end_node_id=d["end_node_id"],
        )


# --- 2. МЕТКА НОМЕРА СМЕЩАЕМАЯ С НАСТРОЙКОЙ ШРИФТА ---
class MovableTextItem(QGraphicsTextItem):
    def __init__(self, text: str, parent_point_item, movable: bool = True):
        super().__init__(text)
        self.parent_point_item = parent_point_item

        flags = QGraphicsItem.ItemIgnoresTransformations
        if movable:
            flags |= QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable

        self.setFlags(flags)
        self.setDefaultTextColor(Qt.black)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.flags() & QGraphicsItem.ItemIsMovable:
            rect = self.boundingRect()
            center_pos = self.pos() + QPointF(rect.width() / 2, rect.height() / 2)
            new_offset = center_pos - self.parent_point_item.pos()
            self.parent_point_item.point.label_offset = (new_offset.x(), new_offset.y())


# --- 3. ГРАФИЧЕСКИЙ ЭЛЕМЕНТ ТОЧКИ ---
class GraphicsPointItem(QGraphicsItem):
    def __init__(
        self, point: MapPoint, scene: QGraphicsScene, on_move_callback=None
    ):
        super().__init__()
        self.point = point
        self.scene_ref = scene
        self.on_move_callback = on_move_callback
        self.radius = 8.0

        self.setFlags(
            QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsFocusable
            | QGraphicsItem.ItemSendsGeometryChanges
            | QGraphicsItem.ItemIgnoresTransformations
        )
        self.setPos(QPointF(point.coords[0], point.coords[1]))

        self.text_item = None
        if self.point.point_type != PointType.CORRIDOR_NODE:
            display_text = self.point.name
            if self.point.alias:
                display_text += f"\n({self.point.alias})"

            is_movable = (self.point.point_type == PointType.ROOM)
            self.text_item = MovableTextItem(display_text, self, movable=is_movable)

            font = QFont("Arial", self.point.font_size, QFont.Bold)
            self.text_item.setFont(font)

            self.scene_ref.addItem(self.text_item)
            self.update_text_position()

    def update_text_position(self):
        if self.text_item:
            rect = self.text_item.boundingRect()
            offset_point = QPointF(self.point.label_offset[0], self.point.label_offset[1])
            target_center = self.pos() + offset_point
            top_left = target_center - QPointF(rect.width() / 2, rect.height() / 2)
            self.text_item.setPos(top_left)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            new_pos = value
            self.point.coords = (new_pos.x(), new_pos.y())
            self.update_text_position()
            if self.on_move_callback:
                self.on_move_callback()
        return super().itemChange(change, value)

    def move_by_offset(self, dx: float, dy: float):
        new_pos = self.pos() + QPointF(dx, dy)
        self.setPos(new_pos)

    def update_text(self):
        if self.text_item:
            display_text = self.point.name
            if self.point.alias:
                display_text += f"\n({self.point.alias})"
            self.text_item.setPlainText(display_text)
            font = QFont("Arial", self.point.font_size, QFont.Bold)
            self.text_item.setFont(font)
            self.update_text_position()

    def remove_associated_items(self):
        if self.text_item and self.text_item.scene():
            self.scene_ref.removeItem(self.text_item)

    def boundingRect(self) -> QRectF:
        r = self.radius
        return QRectF(-r - 6, -r - 6, 2 * r + 12, 2 * r + 12)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)

        if self.point.is_favorite:
            brush_color = QColor(255, 215, 0)
        elif self.point.point_type == PointType.STAIR:
            brush_color = QColor(255, 140, 0)
        elif self.point.point_type == PointType.ROOM:
            brush_color = QColor(46, 139, 87)
        else:
            brush_color = QColor(70, 130, 180)

        painter.setBrush(brush_color)

        if self.isSelected():
            painter.setPen(QPen(QColor(255, 0, 0), 3.5))
        else:
            painter.setPen(QPen(Qt.black, 1.5))

        painter.drawEllipse(QPointF(0.0, 0.0), self.radius, self.radius)


# --- 4. ИНТЕРАКТИВНЫЙ ХОЛСТ ---
class MapCanvasView(QGraphicsView):
    point_clicked_signal = pyqtSignal(QPointF)
    item_selected_signal = pyqtSignal(object)
    delete_requested_signal = pyqtSignal()

    def __init__(self, scene: QGraphicsScene):
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

        self._is_panning = False
        self._pan_start_pos = QPointF()

    def wheelEvent(self, event):
        zoom_factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(zoom_factor, zoom_factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self._is_panning = True
            self._pan_start_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        item = self.itemAt(event.pos())

        if isinstance(item, QGraphicsPixmapItem):
            item = None

        if isinstance(item, GraphicsPointItem):
            self.item_selected_signal.emit(item)
        elif isinstance(item, MovableTextItem):
            self.item_selected_signal.emit(item.parent_point_item)
        else:
            if event.button() == Qt.LeftButton and item is None:
                scene_pos = self.mapToScene(event.pos())
                self.point_clicked_signal.emit(scene_pos)

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_panning:
            delta = event.pos() - self._pan_start_pos
            self._pan_start_pos = event.pos()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y()
            )
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton and self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_requested_signal.emit()
            event.accept()
            return

        selected_items = self.scene().selectedItems()
        point_items = [
            it for it in selected_items if isinstance(it, GraphicsPointItem)
        ]

        if point_items:
            step = 10.0 if event.modifiers() & Qt.ShiftModifier else 2.0
            dx, dy = 0.0, 0.0

            if event.key() == Qt.Key_Left:
                dx = -step
            elif event.key() == Qt.Key_Right:
                dx = step
            elif event.key() == Qt.Key_Up:
                dy = -step
            elif event.key() == Qt.Key_Down:
                dy = step

            if dx != 0.0 or dy != 0.0:
                for item in point_items:
                    item.move_by_offset(dx, dy)
                event.accept()
                return

        super().keyPressEvent(event)


# --- 5. ГЛАВНОЕ ОКНО ПРИЛОЖЕНИЯ ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Навигатор — Редактор планов и графа этажей")
        self.resize(1100, 700)

        self.points_db = {}
        self.corridors = []  # Список объектов CorridorSegment
        self.next_corridor_id = 1
        self.floor_images = {}
        self.floor_image_paths = {}
        self.floors_list = [1]
        self.current_floor = 1
        self.next_point_id = 1

        self.selected_point_for_corridor = None
        self.current_selected_item = None
        self.corridor_lines = []

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        self.scene = QGraphicsScene(-2000, -2000, 4000, 4000)
        self.view = MapCanvasView(self.scene)
        self.view.point_clicked_signal.connect(self.handle_canvas_click)
        self.view.item_selected_signal.connect(self.handle_item_selected)
        self.view.delete_requested_signal.connect(self.delete_selected_point)
        main_layout.addWidget(self.view, stretch=3)

        control_panel = QVBoxLayout()

        # Сохранение / Загрузка
        control_panel.addWidget(QLabel("<b>Файл проекта:</b>"))
        file_io_layout = QHBoxLayout()
        self.save_btn = QPushButton("Сохранить проект")
        self.save_btn.clicked.connect(self.save_project)
        file_io_layout.addWidget(self.save_btn)

        self.load_btn = QPushButton("Загрузить проект")
        self.load_btn.clicked.connect(self.load_project)
        file_io_layout.addWidget(self.load_btn)
        control_panel.addLayout(file_io_layout)

        # Этажи
        control_panel.addWidget(QLabel("<hr><b>Этаж и План карты:</b>"))
        floor_layout = QHBoxLayout()
        self.floor_combo = QComboBox()
        self.update_floor_combo()
        self.floor_combo.currentIndexChanged.connect(self.change_floor)
        floor_layout.addWidget(self.floor_combo)

        self.add_floor_btn = QPushButton("+")
        self.add_floor_btn.setToolTip("Добавить этаж")
        self.add_floor_btn.clicked.connect(self.add_floor)
        floor_layout.addWidget(self.add_floor_btn)

        self.remove_floor_btn = QPushButton("–")
        self.remove_floor_btn.setToolTip("Удалить этаж")
        self.remove_floor_btn.clicked.connect(self.remove_floor)
        floor_layout.addWidget(self.remove_floor_btn)

        control_panel.addLayout(floor_layout)

        self.load_bg_btn = QPushButton("Загрузить фото плана этажа")
        self.load_bg_btn.clicked.connect(self.load_floor_image)
        control_panel.addWidget(self.load_bg_btn)

        # Точки
        control_panel.addWidget(QLabel("<hr><b>Добавление точек:</b>"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Номер кабинета / Название...")
        control_panel.addWidget(self.name_input)

        self.alias_input = QLineEdit()
        self.alias_input.setPlaceholderText("Второе имя (например, Деканат)...")
        control_panel.addWidget(self.alias_input)

        self.add_room_btn = QPushButton("Добавить Дверь/Кабинет")
        self.add_room_btn.setCheckable(True)
        control_panel.addWidget(self.add_room_btn)

        self.add_stair_btn = QPushButton("Добавить Лестницу")
        self.add_stair_btn.setCheckable(True)
        control_panel.addWidget(self.add_stair_btn)

        # Коридоры
        control_panel.addWidget(QLabel("<hr><b>Соединение (Коридоры):</b>"))
        self.connect_mode_btn = QPushButton("Соединить точки (Коридор)")
        self.connect_mode_btn.setCheckable(True)
        control_panel.addWidget(self.connect_mode_btn)

        # Свойства и Удаление
        control_panel.addWidget(QLabel("<hr><b>Свойства выбранной точки:</b>"))

        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("Размер шрифта номера:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 32)
        self.font_size_spin.setValue(10)
        self.font_size_spin.valueChanged.connect(self.update_font_size)
        font_layout.addWidget(self.font_size_spin)
        control_panel.addLayout(font_layout)

        self.fav_checkbox = QCheckBox("В Избранном (Маршруты)")
        self.fav_checkbox.stateChanged.connect(self.toggle_favorite)
        control_panel.addWidget(self.fav_checkbox)

        self.delete_point_btn = QPushButton("Удалить выбранную точку")
        self.delete_point_btn.setStyleSheet(
            "background-color: #ffcccc; color: #990000; font-weight: bold;"
        )
        self.delete_point_btn.clicked.connect(self.delete_selected_point)
        control_panel.addWidget(self.delete_point_btn)

        control_panel.addStretch()
        main_layout.addLayout(control_panel, stretch=1)

    def update_floor_combo(self):
        self.floor_combo.blockSignals(True)
        self.floor_combo.clear()
        for f in self.floors_list:
            self.floor_combo.addItem(f"Этаж {f}")
        idx = (
            self.floors_list.index(self.current_floor)
            if self.current_floor in self.floors_list
            else 0
        )
        self.floor_combo.setCurrentIndex(idx)
        self.floor_combo.blockSignals(False)

    def add_floor(self):
        new_floor = max(self.floors_list) + 1 if self.floors_list else 1
        self.floors_list.append(new_floor)
        self.current_floor = new_floor
        self.update_floor_combo()
        self.redraw_scene()

    def remove_floor(self):
        if len(self.floors_list) <= 1:
            return

        self.points_db = {
            pid: p for pid, p in self.points_db.items() if p.floor != self.current_floor
        }
        self.corridors = [c for c in self.corridors if c.floor != self.current_floor]

        if self.current_floor in self.floor_images:
            del self.floor_images[self.current_floor]
        if self.current_floor in self.floor_image_paths:
            del self.floor_image_paths[self.current_floor]

        self.floors_list.remove(self.current_floor)
        self.current_floor = self.floors_list[0]
        self.update_floor_combo()
        self.redraw_scene()

    def change_floor(self, index: int):
        if 0 <= index < len(self.floors_list):
            self.current_floor = self.floors_list[index]
            self.selected_point_for_corridor = None
            self.current_selected_item = None
            self.redraw_scene()

    def load_floor_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите фото плана этажа",
            "",
            "Изображения (*.png *.jpg *.jpeg *.bmp)",
        )
        if file_path:
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                QMessageBox.warning(self, "Ошибка", "Не удалось загрузить изображение.")
                return

            self.floor_images[self.current_floor] = pixmap
            self.floor_image_paths[self.current_floor] = file_path
            self.redraw_scene()
            self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def delete_selected_point(self):
        selected_items = self.scene.selectedItems()
        target_items = []

        for item in selected_items:
            if isinstance(item, GraphicsPointItem):
                target_items.append(item)
            elif isinstance(item, MovableTextItem):
                target_items.append(item.parent_point_item)

        if not target_items and self.current_selected_item:
            target_items.append(self.current_selected_item)

        target_items = list(set(target_items))

        for point_item in target_items:
            pid = point_item.point.id
            if pid in self.points_db:
                del self.points_db[pid]

            self.corridors = [
                c
                for c in self.corridors
                if c.start_node_id != pid and c.end_node_id != pid
            ]

            point_item.remove_associated_items()

        self.current_selected_item = None
        self.selected_point_for_corridor = None
        self.redraw_scene()

    def handle_canvas_click(self, pos: QPointF):
        if self.connect_mode_btn.isChecked():
            self.selected_point_for_corridor = None
            return

        name = self.name_input.text().strip()
        alias = self.alias_input.text().strip()

        if not name:
            name = f"Точка #{self.next_point_id}"

        if self.add_stair_btn.isChecked():
            p_type = PointType.STAIR
            self.add_stair_btn.setChecked(False)
        elif self.add_room_btn.isChecked():
            p_type = PointType.ROOM
            self.add_room_btn.setChecked(False)
        else:
            p_type = PointType.CORRIDOR_NODE

        new_point = MapPoint(
            id=self.next_point_id,
            name=name,
            floor=self.current_floor,
            coords=(pos.x(), pos.y()),
            point_type=p_type,
            alias=alias,
        )

        self.points_db[new_point.id] = new_point
        self.next_point_id += 1

        self.name_input.clear()
        self.alias_input.clear()
        self.redraw_scene()

    def handle_item_selected(self, item: GraphicsPointItem):
        self.current_selected_item = item
        self.font_size_spin.setValue(item.point.font_size)
        self.fav_checkbox.setChecked(item.point.is_favorite)

        if self.connect_mode_btn.isChecked():
            if self.selected_point_for_corridor is None:
                self.selected_point_for_corridor = item.point
            else:
                p1 = self.selected_point_for_corridor
                p2 = item.point
                if p1.id != p2.id:
                    segment = CorridorSegment(
                        id=self.next_corridor_id,
                        floor=self.current_floor,
                        start_node_id=p1.id,
                        end_node_id=p2.id,
                    )
                    self.next_corridor_id += 1
                    self.corridors.append(segment)
                self.selected_point_for_corridor = None
                self.redraw_scene()

    def update_corridors_lines(self):
        for line_item, id1, id2 in self.corridor_lines:
            if id1 in self.points_db and id2 in self.points_db:
                p1 = self.points_db[id1]
                p2 = self.points_db[id2]
                line_item.setLine(
                    QLineF(
                        QPointF(p1.coords[0], p1.coords[1]),
                        QPointF(p2.coords[0], p2.coords[1]),
                    )
                )

    def update_font_size(self, value: int):
        if self.current_selected_item:
            self.current_selected_item.point.font_size = value
            self.current_selected_item.update_text()

    def toggle_favorite(self, state: int):
        if self.current_selected_item:
            self.current_selected_item.point.is_favorite = state == Qt.Checked
            self.current_selected_item.update()

    def save_project(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить проект", "", "JSON файлы (*.json)"
        )
        if not file_path:
            return

        project_dir = os.path.dirname(file_path)

        relative_image_paths = {}
        for floor_num, img_path in self.floor_image_paths.items():
            try:
                rel_path = os.path.relpath(img_path, project_dir)
                relative_image_paths[str(floor_num)] = rel_path
            except ValueError:
                relative_image_paths[str(floor_num)] = img_path

        data = {
            "floors_list": self.floors_list,
            "next_point_id": self.next_point_id,
            "next_corridor_id": self.next_corridor_id,
            "corridors": [c.to_dict() for c in self.corridors],
            "points": [p.to_dict() for p in self.points_db.values()],
            "floor_images": relative_image_paths,
        }

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            QMessageBox.information(
                self, "Успех", "Данные проекта успешно сохранены!"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось сохранить файл: {e}"
            )

    def load_project(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Загрузить проект", "", "JSON файлы (*.json)"
        )
        if not file_path:
            return

        project_dir = os.path.dirname(file_path)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.floors_list = data.get("floors_list", [1])
            self.next_point_id = data.get("next_point_id", 1)
            self.next_corridor_id = data.get("next_corridor_id", 1)

            # Безопасное чтение коридоров
            raw_corridors = data.get("corridors", [])
            self.corridors = []

            for c in raw_corridors:
                if isinstance(c, dict):
                    # Новый формат: {"id": 1, "floor": 1, "start_node_id": A, "end_node_id": B}
                    self.corridors.append(CorridorSegment.from_dict(c))
                elif isinstance(c, (list, tuple)):
                    # Старый формат: [A, B] или [A, B, ...]
                    p1_id, p2_id = c[0], c[1]
                    p1_floor = 1
                    if data.get("points") and len(data["points"]) > 0:
                        p1_floor = data["points"][0].get("floor", 1)

                    self.corridors.append(
                        CorridorSegment(
                            id=self.next_corridor_id,
                            floor=p1_floor,
                            start_node_id=p1_id,
                            end_node_id=p2_id,
                        )
                    )
                    self.next_corridor_id += 1

            self.points_db = {}
            for p_dict in data.get("points", []):
                p = MapPoint.from_dict(p_dict)
                self.points_db[p.id] = p

            self.floor_image_paths = {}
            self.floor_images = {}

            for floor_str, img_path in data.get("floor_images", {}).items():
                floor_num = int(floor_str)
                full_path = os.path.normpath(os.path.join(project_dir, img_path))

                if not os.path.exists(full_path) and os.path.exists(img_path):
                    full_path = img_path

                if os.path.exists(full_path):
                    pixmap = QPixmap(full_path)
                    if not pixmap.isNull():
                        self.floor_images[floor_num] = pixmap
                        self.floor_image_paths[floor_num] = full_path

            self.current_floor = self.floors_list[0]
            self.update_floor_combo()
            self.redraw_scene()
            QMessageBox.information(
                self, "Успех", "Проект успешно загружен!"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось прочитать проект: {e}"
            )

    def redraw_scene(self):
        self.scene.clear()
        self.corridor_lines.clear()

        # 1. Фото фона
        if self.current_floor in self.floor_images:
            pixmap = self.floor_images[self.current_floor]
            pixmap_item = QGraphicsPixmapItem(pixmap)
            pixmap_item.setPos(
                -pixmap.width() / 2.0, -pixmap.height() / 2.0
            )
            self.scene.addItem(pixmap_item)

            margin = 500
            self.scene.setSceneRect(
                -pixmap.width() / 2.0 - margin,
                -pixmap.height() / 2.0 - margin,
                pixmap.width() + 2 * margin,
                pixmap.height() + 2 * margin,
            )
        else:
            self.scene.setSceneRect(-2000, -2000, 4000, 4000)

        # 2. Коридоры
        pen = QPen(QColor(200, 0, 0), 3, Qt.DashLine)
        for corridor in self.corridors:
            id1 = corridor.start_node_id
            id2 = corridor.end_node_id
            if id1 in self.points_db and id2 in self.points_db:
                p1 = self.points_db[id1]
                p2 = self.points_db[id2]
                if (
                    p1.floor == self.current_floor
                    and p2.floor == self.current_floor
                ):
                    line_item = self.scene.addLine(
                        QLineF(
                            QPointF(p1.coords[0], p1.coords[1]),
                            QPointF(p2.coords[0], p2.coords[1]),
                        ),
                        pen,
                    )
                    self.corridor_lines.append((line_item, id1, id2))

        # 3. Точки текущего этажа
        selected_id = (
            self.current_selected_item.point.id
            if self.current_selected_item
            else None
        )
        self.current_selected_item = None

        for point in self.points_db.values():
            if point.floor == self.current_floor:
                item = GraphicsPointItem(
                    point,
                    self.scene,
                    on_move_callback=self.update_corridors_lines,
                )
                self.scene.addItem(item)

                if point.id == selected_id:
                    item.setSelected(True)
                    item.setFocus()
                    self.current_selected_item = item


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()