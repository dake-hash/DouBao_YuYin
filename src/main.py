"""
main.py — 程序入口

使用方法:
    python src/main.py
    或
    python -m src.main
"""

import sys

from app import DoubaoPetApp


def main() -> None:
    app = DoubaoPetApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
