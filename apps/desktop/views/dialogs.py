from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QLabel, QListWidget, QPushButton, QVBoxLayout


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
            self.list_widget.item(self.list_widget.count() - 1).setData(
                Qt.UserRole, pt
            )

        layout.addWidget(self.list_widget)

        select_btn = QPushButton("Выбрать пункт назначения")
        select_btn.clicked.connect(self.accept_selection)
        layout.addWidget(select_btn)

    def accept_selection(self):
        current_item = self.list_widget.currentItem()
        if current_item:
            self.selected_room = current_item.data(Qt.UserRole)
            self.accept()