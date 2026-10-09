import math
import os
from PyQt5.QtCore import QLineF, QPointF, Qt
from PyQt5.QtGui import QBrush, QColor, QPen, QPixmap, QPolygonF
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from apps.desktop.views.canvas import NavigationCanvasView
from apps.desktop.views.dialogs import FavoritesDialog
from apps.desktop.views.items import GraphicsPointItem
from packages.core.models import PointType
from packages.core.pathfinding import build_full_route
from packages.storage.loader import ProjectData, load_project_from_json


class NavigatorWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Навигатор по корпусу")
        self.resize(1100, 700)

        self.project_data = ProjectData()
        self.floor_images = {}
        self.current_floor = 1
        self.path_points = []

        self.init_ui()
        self.load_project_on_start()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        self.scene = QGraphicsScene(-2000, -2000, 4000, 4000)
        self.view = NavigationCanvasView(self.scene)
        main_layout.addWidget(self.view, stretch=3)

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
        self.build_path_btn.setStyleSheet(
            "background-color: #2e8b57; color: white; font-weight: bold; padding: 6px;"
        )
        self.build_path_btn.clicked.connect(self.build_route)
        control_panel.addWidget(self.build_path_btn)

        self.clear_path_btn = QPushButton("Сбросить маршрут")
        self.clear_path_btn.clicked.connect(self.clear_route)
        control_panel.addWidget(self.clear_path_btn)

        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(
            "color: #0055aa; font-weight: bold; margin-top: 10px;"
        )
        control_panel.addWidget(self.info_label)

        control_panel.addStretch()
        main_layout.addLayout(control_panel, stretch=1)

    def load_project_on_start(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл сохраненного проекта",
            "",
            "JSON файлы (*.json)",
        )
        if not file_path:
            QMessageBox.warning(
                self,
                "Предупреждение",
                "Проект не загружен. Навигатор не может работать без данных.",
            )
            return

        try:
            self.project_data = load_project_from_json(file_path)
            self.floor_images = {}

            missing_images = []
            for floor_num, img_path in self.project_data.floor_image_paths.items():
                if os.path.exists(img_path):
                    pixmap = QPixmap(img_path)
                    if not pixmap.isNull():
                        self.floor_images[floor_num] = pixmap
                    else:
                        missing_images.append(
                            f"Этаж {floor_num}: Не удалось загрузить изображение ({img_path})"
                        )
                else:
                    missing_images.append(
                        f"Этаж {floor_num}: Файл не найден ({img_path})"
                    )

            if missing_images:
                QMessageBox.warning(
                    self,
                    "Предупреждение по изображениям",
                    "Проблемы с фоновыми изображениями:\n"
                    + "\n".join(missing_images),
                )

            self.current_floor = (
                self.project_data.floors_list[0]
                if self.project_data.floors_list
                else 1
            )
            self.update_floor_combo()
            self.populate_room_combos()
            self.redraw_scene()

        except Exception as e:
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось прочитать проект: {e}"
            )

    def update_floor_combo(self):
        self.floor_combo.blockSignals(True)
        self.floor_combo.clear()
        for f in self.project_data.floors_list:
            self.floor_combo.addItem(f"Этаж {f}")
        idx = (
            self.project_data.floors_list.index(self.current_floor)
            if self.current_floor in self.project_data.floors_list
            else 0
        )
        self.floor_combo.setCurrentIndex(idx)
        self.floor_combo.blockSignals(False)

    def populate_room_combos(self):
        self.start_combo.clear()
        self.end_combo.clear()

        rooms = [
            p
            for p in self.project_data.points_db.values()
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
        if 0 <= index < len(self.project_data.floors_list):
            self.current_floor = self.project_data.floors_list[index]
            self.redraw_scene()

    def open_favorites(self):
        favs = [
            p for p in self.project_data.points_db.values() if p.is_favorite
        ]
        if not favs:
            QMessageBox.information(
                self,
                "Избранное",
                "В проекте нет кабинетов, отмеченных как избранное.",
            )
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
            QMessageBox.information(
                self, "Маршрут", "Начальная и конечная точки совпадают."
            )
            return

        route, info = build_full_route(
            self.project_data.points_db,
            self.project_data.corridors,
            start_id,
            end_id,
        )
        if not route:
            QMessageBox.warning(self, "Ошибка", info)
            return

        self.path_points = route
        self.info_label.setText(info)

        start_pt = self.project_data.points_db[start_id]
        self.current_floor = start_pt.floor
        self.update_floor_combo()
        self.redraw_scene()

    def clear_route(self):
        self.path_points = []
        self.info_label.setText("")
        self.redraw_scene()

    def draw_arrows_for_segment(self, p1: QPointF, p2: QPointF, color: QColor):
        """
        Рисует хотя бы одну стрелку на отрезке любого размера.
        На длинных отрезках количество стрелок увеличивается пропорционально длине.
        """
        line_length = math.hypot(p2.x() - p1.x(), p2.y() - p1.y())
        if line_length < 1:
            return

        # Шаг для создания дополнительных стрелок
        step = 60.0
        num_arrows = max(1, int(line_length // step))

        angle = math.atan2(p2.y() - p1.y(), p2.x() - p1.x())
        arrow_size = 12.0
        arrow_angle = math.pi / 6.0

        for i in range(1, num_arrows + 1):
            t = i / (num_arrows + 1)
            target_x = p1.x() + (p2.x() - p1.x()) * t
            target_y = p1.y() + (p2.y() - p1.y()) * t
            target_pt = QPointF(target_x, target_y)

            p_tip = target_pt + QPointF(
                math.cos(angle) * (arrow_size / 2.0),
                math.sin(angle) * (arrow_size / 2.0),
            )
            p_left = p_tip - QPointF(
                math.cos(angle - arrow_angle) * arrow_size,
                math.sin(angle - arrow_angle) * arrow_size,
            )
            p_right = p_tip - QPointF(
                math.cos(angle + arrow_angle) * arrow_size,
                math.sin(angle + arrow_angle) * arrow_size,
            )

            arrow_head = QPolygonF([p_tip, p_left, p_right])
            self.scene.addPolygon(arrow_head, QPen(color), QBrush(color))

    def redraw_scene(self):
        self.scene.clear()

        # 1. Отображение фона плана этажа
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

        # 2. Линия построенного маршрута и стрелки направления
        route_color = QColor(0, 102, 255)
        route_pen = QPen(
            route_color, 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin
        )

        if len(self.path_points) > 1:
            seen_segments = set()
            for i in range(len(self.path_points) - 1):
                pt1 = self.path_points[i]
                pt2 = self.path_points[i + 1]

                if pt1.floor == self.current_floor and pt2.floor == self.current_floor:
                    # Рисуем линию
                    self.scene.addLine(QLineF(pt1.coords, pt2.coords), route_pen)

                    # Рисуем минимум 1 стрелку на отрезок
                    segment_key = (pt1.id, pt2.id)
                    reverse_key = (pt2.id, pt1.id)
                    if segment_key not in seen_segments and reverse_key not in seen_segments:
                        self.draw_arrows_for_segment(pt1.coords, pt2.coords, route_color)
                        seen_segments.add(segment_key)

        # 3. Отображение ключевых точек (кабинеты, лестницы)
        for point in self.project_data.points_db.values():
            if point.floor == self.current_floor:
                item = GraphicsPointItem(point, self.scene)
                item.setZValue(10)
                self.scene.addItem(item)