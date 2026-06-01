import sys
import os
import ctypes

# ======================================================================
# 管理者権限チェック（QApplication より前に実行）
# ======================================================================
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


if not is_admin():
    from PySide6.QtWidgets import QApplication, QMessageBox
    _app = QApplication(sys.argv)
    QMessageBox.critical(
        None,
        "管理者権限が必要です",
        "FWquickSetter は Windows Firewall を変更するため、\n管理者として起動してください。",
    )
    sys.exit(1)

# ======================================================================
# 通常起動
# ======================================================================
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    qss_path = os.path.join(os.path.dirname(__file__), "ui", "style.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()