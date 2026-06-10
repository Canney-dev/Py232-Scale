import sys


try:
    from scale_logger.gui import run
except ModuleNotFoundError as exc:
    missing_package = exc.name or "A REQUIRED PACKAGE"
    print(f"MISSING PYTHON PACKAGE: {missing_package}")
    print("RUN THIS FROM THE PROJECT FOLDER:")
    print("python -m pip install -r requirements.txt")
    sys.exit(1)


if __name__ == "__main__":
    run()
