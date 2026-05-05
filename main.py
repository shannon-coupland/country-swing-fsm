from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from country_swing_fsm.data.static_data import ALL_MOVES, ALL_POSITIONS


def main() -> None:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("PySide6 is not installed.")
        print("Install dependencies with: pip install -e .")
        return

    from country_swing_fsm.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow(positions=ALL_POSITIONS, moves=ALL_MOVES)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
