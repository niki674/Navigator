import os
import sys

# Добавляем корень проекта в PYTHONPATH для запуска из любой папки
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../")
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PyQt5.QtWidgets import QApplication
from apps.desktop.views.main_window import NavigatorWindow


def main():
    app = QApplication(sys.argv)
    window = NavigatorWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()