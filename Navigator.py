import json
import heapq
import math
import sys
import os
from enum import Enum
from typing import Dict, List, Tuple, Optional

from PyQt5.QtCore import Qt, QPointF, QLineF, QRectF
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QComboBox, QPushButton, QFileDialog, QMessageBox,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsItem,
    QGraphicsTextItem, QListWidget, QDialog
)


# --- 1. ГЕОМЕТРИЧЕСКИЙ ДВИЖОК И МАТЕМАТИКА ---
Point2D = Tuple[float, float]


def distance_pt(p1: Point2D, p2: Point2D) -> float:
    """Евклидово расстояние между двумя точками (x, y)."""
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def project_point_onto_segment(p: Point2D, a: Point2D, b: Point2D) -> Tuple[Point2D, float]:
    """
    Возвращает ближайшую точку на отрезке AB относительно точки P
    и квадрат расстояния до нее.
    """
    px, py = p
    ax, ay = a
    bx, by = b

    dx = bx - ax
    dy = by - ay

    if dx == 0 and dy == 0:
        dist_sq = (px - ax) ** 2 + (py - ay) ** 2
        return (ax, ay), dist_sq

    # Коэффициент проекции t = (PA · AB) / |AB|^2
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))

    proj_x = ax + t * dx
    proj_y = ay + t * dy

    dist_sq = (px - proj_x) ** 2 + (py - proj_y) ** 2
    return (proj_x, proj_y), dist_sq


def find_segments_intersection(a1: Point2D, a2: Point2D, b1: Point2D, b2: Point2D) -> Optional[Point2D]:
    """Находит точку пересечения двух отрезков A1A2 и B1B2, если они пересекаются."""
    x1, y1 = a1
    x2, y2 = a2
    x3, y3 = b1
    x4, y4 = b2

    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-9:
        return None

    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom

    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        px = x1 + t * (x2 - x1)
        py = y1 + t * (y2 - y1)
        return (px, py)

    return None


# --- 2. ТИПЫ ТОЧЕК И КЛАССЫ МОДЕЛИ ---
class PointType(Enum):
    REGULAR = "Обычная/Узел"
    ROOM = "Кабинет/Дверь"
    STAIR = "Лестница"
    ELEVATOR = "Лифт"


class MapPoint:
    def __init__(self, point_id: int, name: str, coords: QPointF, floor: int = 1,
                 point_type: PointType = PointType.REGULAR):
        self.id = point_id
        self.name = name
        self.alias = ""
        self.coords = coords  # QPointF
        self.floor = floor
        self.point_type = point_type
        self.is_favorite = False
        self.label_offset = QPointF(0.0, 0.0)
        self.font_size = 10

    @property
    def tuple_coords(self) -> Point2D:
        return (self.coords.x(), self.coords.y())

    @classmethod
    def from_dict(cls, data):
        p_type = PointType.REGULAR
        for t in PointType:
            if t.value == data.get("point_type"):
                p_type = t
                break

        pt = cls(
            point_id=data["id"],
            name=data["name"],
            coords=QPointF(data["x"], data["y"]),
            floor=data["floor"],
            point_type=p_type,
        )
        pt.alias = data.get("alias", "")
        pt.is_favorite = data.get("is_favorite", False)
        pt.label_offset = QPointF(data.get("label_offset_x", 0.0), data.get("label_offset_y", 0.0))
        pt.font_size = data.get("font_size", 10)
        return pt


# --- 3. ЭЛЕМЕНТЫ ОТОБРАЖЕНИЯ НА КАРТЕ ---
class MovableTextItem(QGraphicsTextItem):
    def __init__(self, text: str, parent_point_item):
        super().__init__(text)
        self.parent_point_item = parent_point_item
        self.setFlags(QGraphicsItem.ItemIgnoresTransformations)
        self.setDefaultTextColor(Qt.black)


class GraphicsPointItem(QGraphicsItem):
    def __init__(self, point: MapPoint, scene: QGraphicsScene, is_highlighted: bool = False):
        super().__init__()
        self.point = point
        self.scene_ref = scene
        self.is_highlighted = is_highlighted
        self.radius = 8.0

        self.setFlags(QGraphicsItem.ItemIgnoresTransformations)
        self.setPos(point.coords)

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
            top_left = target_center - QPointF(rect.width() / 2, rect.height() / 2)
            self.text_item.setPos(top_left)

    def boundingRect(self) -> QRectF:
        r = self.radius + 4
        return QRectF(-r, -r, 2 * r, 2 * r)

    def paint(self, painter: QPainter, option, widget=None):
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


# --- 4. ИНТЕРАКТИВНЫЙ ХОЛСТ С ЗУМОМ И ПАННОРАМИРОВАНИЕМ ---
class NavigationCanvasView(QGraphicsView):
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
        if event.button() in (Qt.RightButton, Qt.LeftButton):
            item = self.itemAt(event.pos())
            if item is None or isinstance(item, QGraphicsPixmapItem):
                self._is_panning = True
                self._pan_start_pos = event.pos()
                self.setCursor(Qt.ClosedHandCursor)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_panning:
            delta = event.pos() - self._pan_start_pos
            self._pan_start_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)


# --- 5. ОКНО ИЗБРАННЫХ КАБИНЕТОВ ---
class FavoritesDialog(QDialog):
    def __init__(self, favorites_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Избранные кабинеты")
        self.resize(300, 400)
        self.selected_room = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Выберите кабинет для назначения цели:"))

        self.list_widget = QListWidget()
        for pt in favorites_list:
            display = f"{pt.name} (Этаж {pt.floor})"
            if pt.alias:
                display += f" - {pt.alias}"
            self.list_widget.addItem(display)
            self.list_widget.item(self.list_widget.count() - 1).setData(Qt.UserRole, pt)

        layout.addWidget(self.list_widget)

        select_btn = QPushButton("Выбрать пункт назначения")
        select_btn.clicked.connect(self.accept_selection)
        layout.addWidget(select_btn)

    def accept_selection(self):
        current_item = self.list_widget.currentItem()
        if current_item:
            self.selected_room = current_item.data(Qt.UserRole)
            self.accept()


# --- 6. ДИНАМИЧЕСКИЙ СТРОИТЕЛЬ ГРАФА И ПОИСК ПУТИ ---
class VirtualGraph:
    def __init__(self):
        self.adj: Dict[Point2D, List[Tuple[Point2D, float]]] = {}

    def add_edge(self, p1: Point2D, p2: Point2D):
        dist = distance_pt(p1, p2)
        if dist < 1e-5:
            return
        self.adj.setdefault(p1, []).append((p2, dist))
        self.adj.setdefault(p2, []).append((p1, dist))


def build_floor_virtual_graph(points_db: Dict[int, MapPoint], corridors: List[Tuple[int, int]], floor: int) -> VirtualGraph:
    v_graph = VirtualGraph()

    # Фильтруем коридоры и точки текущего этажа
    floor_corridors = []
    for u, v in corridors:
        if u in points_db and v in points_db:
            if points_db[u].floor == floor and points_db[v].floor == floor:
                floor_corridors.append((points_db[u].tuple_coords, points_db[v].tuple_coords))

    floor_points = [p for p in points_db.values() if p.floor == floor]

    # Обрабатываем каждый отрезок коридора
    for i, (a, b) in enumerate(floor_corridors):
        points_on_segment = [a, b]

        # 1. Точки пересечений с другими отрезками коридоров
        for j, (c_a, c_b) in enumerate(floor_corridors):
            if i == j:
                continue
            intersect = find_segments_intersection(a, b, c_a, c_b)
            if intersect:
                points_on_segment.append(intersect)

        # 2. Проекции кабинетов, дверей и лестниц на этот коридор
        for p in floor_points:
            p_tuple = p.tuple_coords
            proj, _ = project_point_onto_segment(p_tuple, a, b)
            points_on_segment.append(proj)
            v_graph.add_edge(p_tuple, proj)

        # Сортируем все сформированные узлы вдоль отрезка коридора
        points_on_segment = list(set(points_on_segment))
        points_on_segment.sort(key=lambda pt: distance_pt(a, pt))

        # Связываем их в единую цепочку
        for k in range(len(points_on_segment) - 1):
            v_graph.add_edge(points_on_segment[k], points_on_segment[k + 1])

    return v_graph


def dijkstra_search(v_graph: VirtualGraph, start: Point2D, target: Point2D) -> Optional[List[Point2D]]:
    distances = {start: 0.0}
    previous = {}
    pq = [(0.0, start)]

    while pq:
        curr_dist, curr_node = heapq.heappop(pq)

        if curr_node == target:
            path = []
            curr = target
            while curr in previous:
                path.append(curr)
                curr = previous[curr]
            path.append(start)
            return path[::-1]

        if curr_dist > distances.get(curr_node, float('inf')):
            continue

        for neighbor, weight in v_graph.adj.get(curr_node, []):
            dist = curr_dist + weight
            if dist < distances.get(neighbor, float('inf')):
                distances[neighbor] = dist
                previous[neighbor] = curr_node
                heapq.heappush(pq, (dist, neighbor))

    return None


# --- 7. ГЛАВНОЕ ОКНО НАВИГАТОРА ---
class NavigatorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Навигатор по корпусу")
        self.resize(1100, 700)

        self.points_db = {}
        self.corridors = []
        self.floor_images = {}
        self.floors_list = [1]
        self.current_floor = 1
        self.path_points = []  # Список точек пути QPointF

        self.init_ui()
        self.load_project_on_start()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Карта
        self.scene = QGraphicsScene(-2000, -2000, 4000, 4000)
        self.view = NavigationCanvasView(self.scene)
        main_layout.addWidget(self.view, stretch=3)

        # Боковая панель
        control_panel = QVBoxLayout()

        control_panel.addWidget(QLabel("<b>Этаж для просмотра:</b>"))
        self.floor_combo = QComboBox()
        self.floor_combo.currentIndexChanged.connect(self.change_floor)
        control_panel.addWidget(self.floor_combo)

        control_panel.addWidget(QLabel("<hr><b>Маршрут:</b>"))

        control_panel.addWidget(QLabel("Откуда (Текущий кабинет):"))
        self.start_combo = QComboBox()
        control_panel.addWidget(self.start_combo)

        control_panel.addWidget(QLabel("Куда (Цель):"))
        self.end_combo = QComboBox()
        control_panel.addWidget(self.end_combo)

        self.fav_btn = QPushButton("⭐ Избранные кабинеты")
        self.fav_btn.clicked.connect(self.open_favorites)
        control_panel.addWidget(self.fav_btn)

        self.build_path_btn = QPushButton("Построить маршрут")
        self.build_path_btn.setStyleSheet("background-color: #2e8b57; color: white; font-weight: bold; padding: 6px;")
        self.build_path_btn.clicked.connect(self.build_route)
        control_panel.addWidget(self.build_path_btn)

        self.clear_path_btn = QPushButton("Сбросить маршрут")
        self.clear_path_btn.clicked.connect(self.clear_route)
        control_panel.addWidget(self.clear_path_btn)

        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #0055aa; font-weight: bold; margin-top: 10px;")
        control_panel.addWidget(self.info_label)

        control_panel.addStretch()
        main_layout.addLayout(control_panel, stretch=1)

    def load_project_on_start(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл сохраненного проекта", "", "JSON файлы (*.json)"
        )
        if not file_path:
            QMessageBox.warning(self, "Предупреждение", "Проект не загружен. Навигатор не может работать без данных.")
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            base_dir = os.path.dirname(os.path.abspath(file_path))
            self.floors_list = data.get("floors_list", [1])
            self.corridors = [tuple(c) for c in data.get("corridors", [])]

            self.points_db = {}
            for p_dict in data.get("points", []):
                p = MapPoint.from_dict(p_dict)
                self.points_db[p.id] = p

            floor_paths = {int(k): v for k, v in data.get("floor_images", {}).items()}
            self.floor_images = {}
            for floor_num, relative_img_path in floor_paths.items():
                img_path = relative_img_path if os.path.isabs(relative_img_path) else os.path.join(base_dir, relative_img_path)
                if os.path.exists(img_path):
                    pixmap = QPixmap(img_path)
                    if not pixmap.isNull():
                        self.floor_images[floor_num] = pixmap

            self.current_floor = self.floors_list[0]
            self.update_floor_combo()
            self.populate_room_combos()
            self.redraw_scene()

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось прочитать проект: {e}")

    def update_floor_combo(self):
        self.floor_combo.blockSignals(True)
        self.floor_combo.clear()
        for f in self.floors_list:
            self.floor_combo.addItem(f"Этаж {f}")
        idx = self.floors_list.index(self.current_floor) if self.current_floor in self.floors_list else 0
        self.floor_combo.setCurrentIndex(idx)
        self.floor_combo.blockSignals(False)

    def populate_room_combos(self):
        self.start_combo.clear()
        self.end_combo.clear()

        rooms = [
            p for p in self.points_db.values()
            if p.point_type in (PointType.ROOM, PointType.STAIR)
        ]
        rooms.sort(key=lambda x: (x.floor, x.name))

        for r in rooms:
            display = f"[{r.floor} эт.] {r.name}"
            if r.alias:
                display += f" ({r.alias})"
            self.start_combo.addItem(display, r.id)
            self.end_combo.addItem(display, r.id)

    def change_floor(self, index: int):
        if 0 <= index < len(self.floors_list):
            self.current_floor = self.floors_list[index]
            self.redraw_scene()

    def open_favorites(self):
        favs = [p for p in self.points_db.values() if p.is_favorite]
        if not favs:
            QMessageBox.information(self, "Избранное", "В проекте нет кабинетов, отмеченных как избранное.")
            return

        dialog = FavoritesDialog(favs, self)
        if dialog.exec_() == QDialog.Accepted and dialog.selected_room:
            target_id = dialog.selected_room.id
            index = self.end_combo.findData(target_id)
            if index >= 0:
                self.end_combo.setCurrentIndex(index)

    def build_route(self):
        start_id = self.start_combo.currentData()
        end_id = self.end_combo.currentData()

        if not start_id or not end_id:
            return

        if start_id == end_id:
            QMessageBox.information(self, "Маршрут", "Начальная и конечная точки совпадают.")
            return

        start_pt = self.points_db[start_id]
        end_pt = self.points_db[end_id]

        # 1. Построение маршрута на одном этаже
        if start_pt.floor == end_pt.floor:
            v_graph = build_floor_virtual_graph(self.points_db, self.corridors, start_pt.floor)
            coord_path = dijkstra_search(v_graph, start_pt.tuple_coords, end_pt.tuple_coords)

            if not coord_path:
                QMessageBox.warning(self, "Ошибка", "Не удалось проложить путь между указанными точками.")
                return

            self.path_points = [(start_pt.floor, QPointF(x, y)) for x, y in coord_path]
            self.info_label.setText(f"Маршрут построен по {start_pt.floor} этажу.")

        # 2. Построение маршрута между разными этажами
        else:
            stairs_start = [p for p in self.points_db.values() if p.floor == start_pt.floor and p.point_type == PointType.STAIR]
            stairs_end = [p for p in self.points_db.values() if p.floor == end_pt.floor and p.point_type == PointType.STAIR]

            if not stairs_start or not stairs_end:
                QMessageBox.warning(self, "Ошибка", "Не найдены лестницы для перехода между этажами.")
                return

            v_graph_start = build_floor_virtual_graph(self.points_db, self.corridors, start_pt.floor)
            v_graph_end = build_floor_virtual_graph(self.points_db, self.corridors, end_pt.floor)

            best_path = None
            best_dist = float('inf')
            best_stair_name = ""

            for st1 in stairs_start:
                path1 = dijkstra_search(v_graph_start, start_pt.tuple_coords, st1.tuple_coords)
                if not path1:
                    continue

                st2 = next((s for s in stairs_end if s.name == st1.name), None)
                if not st2:
                    st2 = min(stairs_end, key=lambda s: distance_pt(st1.tuple_coords, s.tuple_coords))

                path2 = dijkstra_search(v_graph_end, st2.tuple_coords, end_pt.tuple_coords)
                if not path2:
                    continue

                d1 = sum(distance_pt(path1[k], path1[k + 1]) for k in range(len(path1) - 1))
                d2 = sum(distance_pt(path2[k], path2[k + 1]) for k in range(len(path2) - 1))

                if (d1 + d2) < best_dist:
                    best_dist = d1 + d2
                    best_path = (start_pt.floor, path1, end_pt.floor, path2)
                    best_stair_name = st1.name

            if not best_path:
                QMessageBox.warning(self, "Ошибка", "Не удалось построить сквозной маршрут через этажи.")
                return

            fl1, p1, fl2, p2 = best_path
            self.path_points = [(fl1, QPointF(x, y)) for x, y in p1] + [(fl2, QPointF(x, y)) for x, y in p2]
            self.info_label.setText(f"Переход с {fl1} на {fl2} этаж через лестницу '{best_stair_name}'.")

        self.current_floor = start_pt.floor
        self.update_floor_combo()
        self.redraw_scene()

    def clear_route(self):
        self.path_points = []
        self.info_label.setText("")
        self.redraw_scene()

    # --- ОТРИСОВКА СЦЕНЫ ---
    def redraw_scene(self):
        self.scene.clear()

        # 1. Отображение плана этажа
        if self.current_floor in self.floor_images:
            pixmap = self.floor_images[self.current_floor]
            pixmap_item = QGraphicsPixmapItem(pixmap)
            pixmap_item.setPos(-pixmap.width() / 2.0, -pixmap.height() / 2.0)
            pixmap_item.setZValue(-100)
            self.scene.addItem(pixmap_item)

            margin = 1000.0
            self.scene.setSceneRect(
                -pixmap.width() / 2.0 - margin,
                -pixmap.height() / 2.0 - margin,
                pixmap.width() + 2 * margin,
                pixmap.height() + 2 * margin,
            )
        else:
            self.scene.setSceneRect(-2000, -2000, 4000, 4000)

        # 2. Отрезки основных коридоров
        corridor_pen = QPen(QColor(180, 180, 180, 120), 2, Qt.DashLine)
        for u, v in self.corridors:
            if u in self.points_db and v in self.points_db:
                p1 = self.points_db[u]
                p2 = self.points_db[v]
                if p1.floor == self.current_floor and p2.floor == self.current_floor:
                    self.scene.addLine(QLineF(p1.coords, p2.coords), corridor_pen)

        # 3. Подсветка маршрута на текущем этаже
        route_pen = QPen(QColor(0, 102, 255), 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        current_floor_route = [pt_coords for fl, pt_coords in self.path_points if fl == self.current_floor]

        if len(current_floor_route) > 1:
            for i in range(len(current_floor_route) - 1):
                p1 = current_floor_route[i]
                p2 = current_floor_route[i + 1]
                self.scene.addLine(QLineF(p1, p2), route_pen)

        # 4. Отрисовка точек карт
        highlight_coords = [pt for pt in current_floor_route]
        for point in self.points_db.values():
            if point.floor == self.current_floor:
                is_on_route = any(
                    abs(point.coords.x() - h.x()) < 1e-3 and abs(point.coords.y() - h.y()) < 1e-3
                    for h in highlight_coords
                )
                item = GraphicsPointItem(point, self.scene, is_highlighted=is_on_route)
                self.scene.addItem(item)


def main():
    app = QApplication(sys.argv)
    window = NavigatorWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()