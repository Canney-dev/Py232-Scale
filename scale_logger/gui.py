import sys
import re
import ctypes
import time

import serial
from serial.tools import list_ports

from PySide6.QtCore import QSettings, QThread, Qt, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QDesktopServices, QPalette
from PySide6.QtPrintSupport import QPrinterInfo
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStyleFactory,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .core import (
    DEFAULT_BAUDRATE,
    DEFAULT_PORT,
    LOG_FOLDER,
    PROJECT_DIR,
    WEIGHTS_PER_ITEM,
    Item,
    QcWorkbookSession,
    caps,
    clean_scale_line,
    is_zero,
    parse_scale_line,
    rank_weight_statuses,
    title_text,
)


THEME_OPTIONS = {
    "system": "System Default",
    "light": "Light",
    "dark": "Dark",
}


def default_style_name():
    app = QApplication.instance()
    if app is None:
        return ""

    return str(app.property("defaultStyleName") or app.style().objectName())


def default_palette():
    app = QApplication.instance()
    if app is None:
        return QPalette()

    palette = app.property("defaultPalette")
    if isinstance(palette, QPalette):
        return QPalette(palette)

    return QPalette(app.palette())


def light_palette():
    style = QStyleFactory.create("Fusion")
    if style is not None:
        return style.standardPalette()

    return QPalette()


def dark_palette():
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(32, 32, 32))
    palette.setColor(QPalette.WindowText, QColor(245, 245, 245))
    palette.setColor(QPalette.Base, QColor(24, 24, 24))
    palette.setColor(QPalette.AlternateBase, QColor(45, 45, 45))
    palette.setColor(QPalette.ToolTipBase, QColor(245, 245, 245))
    palette.setColor(QPalette.ToolTipText, QColor(20, 20, 20))
    palette.setColor(QPalette.Text, QColor(245, 245, 245))
    palette.setColor(QPalette.Button, QColor(45, 45, 45))
    palette.setColor(QPalette.ButtonText, QColor(245, 245, 245))
    palette.setColor(QPalette.BrightText, QColor(255, 80, 80))
    palette.setColor(QPalette.Link, QColor(80, 160, 255))
    palette.setColor(QPalette.Highlight, QColor(64, 128, 200))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(140, 140, 140))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(140, 140, 140))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(140, 140, 140))
    return palette


def apply_theme(theme):
    app = QApplication.instance()
    if app is None:
        return

    if theme == "dark":
        fusion_style = QStyleFactory.create("Fusion")
        if fusion_style is not None:
            QApplication.setStyle(fusion_style)
        app.setPalette(dark_palette())
        return

    if theme == "light":
        fusion_style = QStyleFactory.create("Fusion")
        if fusion_style is not None:
            QApplication.setStyle(fusion_style)
        app.setPalette(light_palette())
        return

    style_name = default_style_name()
    if style_name:
        QApplication.setStyle(style_name)
    app.setPalette(default_palette())


class SerialReader(QThread):
    reading_received = Signal(dict)
    raw_line_received = Signal(str)
    message = Signal(str)
    failed = Signal(str)

    def __init__(self, port, baudrate, dtr_enabled=False, rts_enabled=False):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.dtr_enabled = dtr_enabled
        self.rts_enabled = rts_enabled
        self._running = True
        self._serial = None

    def run(self):
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )
            self._serial.dtr = self.dtr_enabled
            self._serial.rts = self.rts_enabled
            self._serial.reset_input_buffer()
            self.message.emit(f"Connected To {self.port}")

            while self._running:
                raw = self._serial.readline()
                if not raw:
                    continue

                line = clean_scale_line(raw.decode("ascii", errors="ignore"))
                if not line:
                    continue

                self.raw_line_received.emit(line)
                parsed = parse_scale_line(line)
                if parsed:
                    self.reading_received.emit(parsed)
                elif self.should_log_unparsed(line):
                    self.message.emit(f"Unparsed Scale Line: {line}")

        except Exception as exc:
            self.failed.emit(caps(exc))
        finally:
            if self._serial and self._serial.is_open:
                self._serial.close()
            self.message.emit("Serial Port Closed.")

    def stop(self):
        self._running = False

    def request_weight(self):
        if not self._serial or not self._serial.is_open:
            return

        for command in (b"P\r\n", b"p\r\n", b"W\r\n", b"w\r\n"):
            self._serial.write(command)
            self._serial.flush()

    @staticmethod
    def should_log_unparsed(line):
        upper_line = caps(line)
        ignored_prefixes = (
            "DATE:",
            "TIME:",
            "GROSS:",
            "TARE:",
            "MERCHANDISE:",
            "PIECE WEIGHT:",
            "COUNT:",
            "================",
            "----------------",
        )
        return not upper_line.startswith(ignored_prefixes)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PY 232 Scale")
        self.resize(980, 680)

        self.settings = QSettings()
        self.theme_actions = {}
        self.session = None
        self.reader = None
        self.latest_reading = None
        self.latest_raw_line = ""
        self.current_item_index = 0
        self.current_weight_number = 1
        self.current_readings = []
        self.current_raw_rows = []
        self.continue_single_item = False

        self.project_edit = QLineEdit()
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.baud_spin = QSpinBox()
        self.baud_spin.setRange(300, 115200)
        self.baud_spin.setValue(DEFAULT_BAUDRATE)
        self.dtr_check = QCheckBox("DTR")
        self.rts_check = QCheckBox("RTS")
        self.item_edit = QLineEdit()
        self.description_edit = QLineEdit()
        self.items_table = QTableWidget(0, 2)
        self.captured_table = QTableWidget(0, 5)
        self.live_label = QLabel("No Scale Reading")
        self.raw_line_label = QLabel("Raw Serial: None")
        self.target_label = QLabel("Add Items, Then Start Logging.")
        self.serial_settings_label = QLabel("")
        self.log_path_label = QLabel("")
        self.status_box = QTextEdit()

        self.start_button = QPushButton("Start")
        self.continue_item_button = QPushButton("Continue Selected Item")
        self.capture_button = QPushButton("Capture Weight")
        self.stop_button = QPushButton("Stop")
        self.add_item_button = QPushButton("Add Item")
        self.edit_item_button = QPushButton("Edit Selected Item")
        self.remove_item_button = QPushButton("Remove Selected")
        self.edit_weight_button = QPushButton("Edit Selected Weight")
        self.request_weight_button = QPushButton("Request Weight")
        self.open_logs_button = QPushButton("Open Logs Folder")

        self.setup_ui()
        self.load_ports()
        self.set_logging_enabled(False)

    def setup_ui(self):
        self.setup_menu()

        root = QWidget()
        root_layout = QVBoxLayout(root)

        setup_group = QGroupBox("Setup")
        setup_layout = QGridLayout(setup_group)
        setup_layout.addWidget(QLabel("Project #"), 0, 0)
        setup_layout.addWidget(self.project_edit, 0, 1, 1, 4)
        setup_layout.addWidget(self.serial_settings_label, 0, 5, 1, 3)

        item_form = QFormLayout()
        item_form.addRow("Item", self.item_edit)
        item_form.addRow("Description", self.description_edit)

        item_buttons = QHBoxLayout()
        item_buttons.addWidget(self.add_item_button)
        item_buttons.addWidget(self.edit_item_button)
        item_buttons.addWidget(self.remove_item_button)
        item_buttons.addStretch()

        self.items_table.setHorizontalHeaderLabels(["Item", "Description"])
        self.items_table.horizontalHeader().setStretchLastSection(True)
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.items_table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.AnyKeyPressed
        )

        setup_layout.addLayout(item_form, 1, 0, 1, 6)
        setup_layout.addLayout(item_buttons, 2, 0, 1, 6)
        setup_layout.addWidget(self.items_table, 3, 0, 1, 6)

        live_group = QGroupBox("Live Scale")
        live_layout = QVBoxLayout(live_group)
        self.live_label.setAlignment(Qt.AlignCenter)
        self.live_label.setStyleSheet("font-size: 30px; font-weight: 700;")
        self.raw_line_label.setAlignment(Qt.AlignCenter)
        self.raw_line_label.setStyleSheet("font-size: 13px;")
        self.target_label.setAlignment(Qt.AlignCenter)
        self.target_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        live_layout.addWidget(self.live_label)
        live_layout.addWidget(self.raw_line_label)
        live_layout.addWidget(self.target_label)

        action_layout = QHBoxLayout()
        action_layout.addWidget(self.start_button)
        action_layout.addWidget(self.continue_item_button)
        action_layout.addWidget(self.capture_button)
        action_layout.addWidget(self.request_weight_button)
        action_layout.addWidget(self.edit_weight_button)
        action_layout.addWidget(self.stop_button)
        action_layout.addWidget(self.open_logs_button)

        self.captured_table.setHorizontalHeaderLabels([
            "Item",
            "Weight #",
            "Weight",
            "Unit",
            "QC Status",
        ])
        self.captured_table.horizontalHeader().setStretchLastSection(True)
        self.captured_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.captured_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.status_box.setReadOnly(True)
        self.status_box.setMinimumHeight(130)

        root_layout.addWidget(setup_group)
        root_layout.addWidget(live_group)
        root_layout.addLayout(action_layout)
        root_layout.addWidget(QLabel("Captured Weights"))
        root_layout.addWidget(self.captured_table)
        root_layout.addWidget(QLabel("Log File"))
        root_layout.addWidget(self.log_path_label)
        root_layout.addWidget(QLabel("Status"))
        root_layout.addWidget(self.status_box)

        self.setCentralWidget(root)

        self.add_item_button.clicked.connect(self.add_item)
        self.edit_item_button.clicked.connect(self.edit_selected_item)
        self.remove_item_button.clicked.connect(self.remove_selected_item)
        self.items_table.itemChanged.connect(self.uppercase_item_cell)
        self.items_table.itemChanged.connect(self.sync_item_edit)
        self.start_button.clicked.connect(self.start_logging)
        self.continue_item_button.clicked.connect(self.continue_selected_item)
        self.capture_button.clicked.connect(self.capture_weight)
        self.request_weight_button.clicked.connect(self.request_weight)
        self.edit_weight_button.clicked.connect(self.edit_selected_weight)
        self.stop_button.clicked.connect(self.stop_logging)
        self.open_logs_button.clicked.connect(self.open_logs_folder)

    def setup_menu(self):
        file_menu = self.menuBar().addMenu("File")
        open_log_action = QAction("Open Log", self)
        open_log_action.triggered.connect(self.open_existing_log)
        file_menu.addAction(open_log_action)

        save_log_action = QAction("Save Log", self)
        save_log_action.triggered.connect(self.save_current_log)
        file_menu.addAction(save_log_action)

        print_log_action = QAction("Print Log", self)
        print_log_action.triggered.connect(self.print_current_log)
        file_menu.addAction(print_log_action)

        close_action = QAction("Close", self)
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)

        settings_menu = self.menuBar().addMenu("Settings")
        serial_settings_action = QAction("Serial Settings", self)
        serial_settings_action.triggered.connect(self.open_serial_settings)
        settings_menu.addAction(serial_settings_action)

        com_port_test_action = QAction("Com Port Test", self)
        com_port_test_action.triggered.connect(self.run_com_port_test)
        settings_menu.addAction(com_port_test_action)

        receive_test_action = QAction("Receive Test", self)
        receive_test_action.triggered.connect(self.run_receive_test)
        settings_menu.addAction(receive_test_action)

        theme_menu = settings_menu.addMenu("Theme")
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        current_theme = self.current_theme()

        for theme, label in THEME_OPTIONS.items():
            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(theme)
            action.setChecked(theme == current_theme)
            action.triggered.connect(lambda _checked=False, value=theme: self.set_theme(value))
            theme_group.addAction(action)
            theme_menu.addAction(action)
            self.theme_actions[theme] = action

    def load_ports(self):
        ports = [port.device for port in list_ports.comports()]
        if not ports:
            ports = [DEFAULT_PORT]

        current_port = self.port_combo.currentText()
        self.port_combo.clear()
        self.port_combo.addItems(ports)

        if current_port in ports:
            self.port_combo.setCurrentText(current_port)
        elif DEFAULT_PORT in ports:
            self.port_combo.setCurrentText(DEFAULT_PORT)
        else:
            self.port_combo.setCurrentText(ports[0])

        self.update_serial_settings_label()

    def update_serial_settings_label(self):
        dtr = "ON" if self.dtr_check.isChecked() else "OFF"
        rts = "ON" if self.rts_check.isChecked() else "OFF"
        self.serial_settings_label.setText(
            f"Serial: {self.port_combo.currentText()} | "
            f"{self.baud_spin.value()} | DTR {dtr} | RTS {rts}"
        )

    def open_serial_settings(self):
        if self.reader:
            QMessageBox.warning(
                self,
                "Serial Settings",
                "Stop Logging Before Changing Serial Settings.",
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Serial Settings")
        layout = QVBoxLayout(dialog)

        help_text = QLabel(
            "Port Selects The Scale Connection. Baudrate Must Match The Scale. "
            "DTR And RTS Are Serial Control Signals Some Scales Require Before "
            "They Will Send Data."
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

        form_layout = QFormLayout()
        layout.addLayout(form_layout)

        port_combo = QComboBox()
        port_combo.setEditable(True)
        ports = [port.device for port in list_ports.comports()]
        if not ports:
            ports = [DEFAULT_PORT]
        port_combo.addItems(ports)
        port_combo.setCurrentText(self.port_combo.currentText())

        baud_spin = QSpinBox()
        baud_spin.setRange(300, 115200)
        baud_spin.setValue(self.baud_spin.value())

        dtr_check = QCheckBox("DTR")
        dtr_check.setChecked(self.dtr_check.isChecked())
        rts_check = QCheckBox("RTS")
        rts_check.setChecked(self.rts_check.isChecked())

        port_help = QLabel(
            "The Windows COM Port For The Scale, For Example COM4. "
            "Use Receive Test If You Are Not Sure."
        )
        port_help.setWordWrap(True)

        baud_help = QLabel(
            "The Speed Used By The Scale. 9600 Is Common, But It Must Match "
            "The Scale Configuration."
        )
        baud_help.setWordWrap(True)

        dtr_help = QLabel(
            "DTR Means Data Terminal Ready. Some USB/Serial Adapters Or Scales "
            "Only Send Data When This Signal Is On."
        )
        dtr_help.setWordWrap(True)

        rts_help = QLabel(
            "RTS Means Request To Send. Some Scales Use This As A Handshake "
            "Signal Before Transmitting Weight Data."
        )
        rts_help.setWordWrap(True)

        form_layout.addRow("Port", port_combo)
        form_layout.addRow("", port_help)
        form_layout.addRow("Baudrate", baud_spin)
        form_layout.addRow("", baud_help)
        form_layout.addRow("", dtr_check)
        form_layout.addRow("", dtr_help)
        form_layout.addRow("", rts_check)
        form_layout.addRow("", rts_help)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return

        self.port_combo.setCurrentText(port_combo.currentText())
        self.baud_spin.setValue(baud_spin.value())
        self.dtr_check.setChecked(dtr_check.isChecked())
        self.rts_check.setChecked(rts_check.isChecked())
        self.update_serial_settings_label()
        self.log("Serial Settings Updated.")

    def current_theme(self):
        theme = str(self.settings.value("theme", "system"))
        if theme not in THEME_OPTIONS:
            return "system"

        return theme

    def set_theme(self, theme):
        if theme not in THEME_OPTIONS:
            theme = "system"

        self.settings.setValue("theme", theme)
        apply_theme(theme)

        for action_theme, action in self.theme_actions.items():
            action.setChecked(action_theme == theme)

        self.log(f"Theme Set To {THEME_OPTIONS[theme]}.")

    def add_item(self):
        item_name = title_text(self.item_edit.text())
        description = title_text(self.description_edit.text())

        if not item_name:
            QMessageBox.warning(self, "Item Required", "Enter An Item Name Or Number.")
            return

        row = self.items_table.rowCount()
        self.items_table.insertRow(row)
        self.items_table.setItem(row, 0, QTableWidgetItem(item_name))
        self.items_table.setItem(row, 1, QTableWidgetItem(description))
        self.item_edit.clear()
        self.description_edit.clear()
        self.item_edit.setFocus()

    def remove_selected_item(self):
        if self.session:
            QMessageBox.warning(
                self,
                "Logging Started",
                "Items Cannot Be Removed After Logging Starts. Edit The Item Instead.",
            )
            return

        rows = sorted(
            {index.row() for index in self.items_table.selectedIndexes()},
            reverse=True,
        )
        for row in rows:
            self.items_table.removeRow(row)

    def edit_selected_item(self):
        selected_rows = sorted({index.row() for index in self.items_table.selectedIndexes()})
        if not selected_rows:
            QMessageBox.warning(self, "No Item Selected", "Select An Item To Edit.")
            return

        row = selected_rows[0]
        name_item = self.items_table.item(row, 0)
        description_item = self.items_table.item(row, 1)
        current_name = name_item.text() if name_item else ""
        current_description = description_item.text() if description_item else ""

        new_name, ok = QInputDialog.getText(
            self,
            "Edit Item",
            "Item:",
            text=current_name,
        )
        if not ok:
            return

        new_description, ok = QInputDialog.getText(
            self,
            "Edit Description",
            "Description:",
            text=current_description,
        )
        if not ok:
            return

        self.items_table.blockSignals(True)
        self.items_table.setItem(row, 0, QTableWidgetItem(title_text(new_name)))
        self.items_table.setItem(row, 1, QTableWidgetItem(title_text(new_description)))
        self.items_table.blockSignals(False)
        self.sync_item_row(row)

    def items(self):
        result = []
        for row in range(self.items_table.rowCount()):
            item = self.items_table.item(row, 0)
            description = self.items_table.item(row, 1)
            result.append(Item(item.text(), description.text() if description else ""))
        return result

    def uppercase_item_cell(self, item):
        text = title_text(item.text())
        if item.text() == text:
            return

        self.items_table.blockSignals(True)
        item.setText(text)
        self.items_table.blockSignals(False)

    def sync_item_edit(self, item):
        self.sync_item_row(item.row())

    def sync_item_row(self, row):
        if not self.session:
            return

        if row >= len(self.session.items):
            return

        name_item = self.items_table.item(row, 0)
        description_item = self.items_table.item(row, 1)
        name = name_item.text() if name_item else ""
        description = description_item.text() if description_item else ""

        self.session.update_item(row, name, description)
        self.refresh_captured_item_names(row)
        self.update_target()
        self.log(f"Updated Item {row + 1}: {title_text(name)}")

    def start_logging(self):
        items = self.items()
        if not items:
            QMessageBox.warning(self, "No Items", "Add At Least One Item Before Starting.")
            return

        self.session = QcWorkbookSession(self.project_edit.text(), items)
        self.log_path_label.setText(str(self.session.filename))
        self.current_item_index = 0
        self.current_weight_number = 1
        self.current_readings = []
        self.current_raw_rows = []
        self.continue_single_item = False
        self.latest_reading = None
        self.latest_raw_line = ""
        self.live_label.setText("No Scale Reading")
        self.raw_line_label.setText("Raw Serial: None")
        self.captured_table.setRowCount(0)

        self.start_reader()

        self.set_setup_enabled(False)
        self.set_logging_enabled(True)
        self.update_target()
        self.log(f"STARTED NEW LOG: {self.session.filename}")

    def continue_selected_item(self):
        if not self.session:
            QMessageBox.warning(self, "No Log Open", "Open Or Start A Log First.")
            return

        selected_rows = sorted({index.row() for index in self.items_table.selectedIndexes()})
        if not selected_rows:
            QMessageBox.warning(self, "No Item Selected", "Select An Item To Continue.")
            return

        item_index = selected_rows[0]
        if item_index >= len(self.session.items):
            return

        if item_index in self.session.item_results:
            answer = QMessageBox.question(
                self,
                "Replace Item Weights",
                (
                    "This Item Already Has Three Recorded Weights.\n\n"
                    "Continuing Will Replace The Item's Active Low/High Results "
                    "With The Next Three Weights You Capture. Old Raw Rows Will "
                    "Remain In Raw Data For Traceability.\n\n"
                    "Continue?"
                ),
            )
            if answer != QMessageBox.Yes:
                return
            self.remove_captured_rows_for_item(item_index)

        self.current_item_index = item_index
        self.current_weight_number = 1
        self.current_readings = []
        self.current_raw_rows = []
        self.continue_single_item = True
        self.latest_reading = None
        self.live_label.setText("No Scale Reading")
        self.start_reader()
        self.set_setup_enabled(False)
        self.set_logging_enabled(True)
        self.update_target()
        self.log(f"CONTINUING ITEM {item_index + 1}: {self.session.items[item_index].name}")

    def start_reader(self):
        if self.reader:
            return

        self.reader = SerialReader(
            self.port_combo.currentText(),
            self.baud_spin.value(),
            self.dtr_check.isChecked(),
            self.rts_check.isChecked(),
        )
        self.reader.reading_received.connect(self.on_reading)
        self.reader.raw_line_received.connect(self.on_raw_line)
        self.reader.message.connect(self.log)
        self.reader.failed.connect(self.on_serial_error)
        self.reader.start()

    def open_existing_log(self):
        if self.reader:
            QMessageBox.warning(
                self,
                "Open Log",
                "Stop Logging Before Opening A Saved Log.",
            )
            return

        filename, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Open Saved Log",
            str(self.default_log_open_folder()),
            "EXCEL LOGS (*.xlsx)",
        )
        if not filename:
            return

        try:
            self.session = QcWorkbookSession.from_file(filename)
        except Exception as exc:
            QMessageBox.critical(self, "Open Log", str(exc))
            return

        self.project_edit.setText(self.session.project_number)
        self.log_path_label.setText(str(self.session.filename))
        self.current_item_index = 0
        self.current_weight_number = 1
        self.current_readings = []
        self.current_raw_rows = []
        self.latest_reading = None
        self.latest_raw_line = ""
        self.live_label.setText("Saved Log Opened")
        self.raw_line_label.setText("Raw Serial: None")
        self.populate_items_from_session()
        self.populate_captured_weights_from_session()
        self.set_setup_enabled(True)
        self.capture_button.setEnabled(False)
        self.request_weight_button.setEnabled(False)
        self.edit_weight_button.setEnabled(True)
        self.continue_item_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.target_label.setText("Saved Log Opened For Editing.")
        self.log(f"OPENED SAVED LOG: {self.session.filename}")

    def save_current_log(self):
        if not self.session:
            QMessageBox.warning(
                self,
                "Save Log",
                "No Log Is Currently Open.",
            )
            return

        try:
            self.session.save()
        except Exception as exc:
            QMessageBox.critical(self, "Save Log", str(exc))
            return

        self.log_path_label.setText(str(self.session.filename))
        self.log(f"SAVED LOG: {self.session.filename}")
        QMessageBox.information(
            self,
            "Save Log",
            f"Saved:\n{self.session.filename}",
        )

    def print_current_log(self):
        if not self.session:
            QMessageBox.warning(
                self,
                "Print Log",
                "No Log Is Currently Open.",
            )
            return

        printers = [printer.printerName() for printer in QPrinterInfo.availablePrinters()]
        if not printers:
            QMessageBox.warning(
                self,
                "Print Log",
                "No Printers Were Found.",
            )
            return

        default_printer = QPrinterInfo.defaultPrinter().printerName()
        selected_printer, ok = QInputDialog.getItem(
            self,
            "Print Log",
            "Printer:",
            printers,
            printers.index(default_printer) if default_printer in printers else 0,
            False,
        )
        if not ok or not selected_printer:
            return

        try:
            self.session.save()
            result = ctypes.windll.shell32.ShellExecuteW(
                None,
                "printto",
                str(self.session.filename),
                f'"{selected_printer}"',
                None,
                0,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Print Log", str(exc))
            return

        if result <= 32:
            QMessageBox.critical(
                self,
                "Print Log",
                (
                    "Windows Could Not Send This Workbook To The Printer. "
                    "Make Sure .xlsx Files Open With Excel Or Another App "
                    "That Supports Printing."
                ),
            )
            return

        self.log(f"SENT LOG TO PRINTER {selected_printer}: {self.session.filename}")
        QMessageBox.information(
            self,
            "Print Log",
            f"Sent To {selected_printer}:\n{self.session.filename}",
        )

    @staticmethod
    def default_log_open_folder():
        if LOG_FOLDER.exists():
            return LOG_FOLDER

        legacy_folder = PROJECT_DIR / "logs"
        if legacy_folder.exists():
            return legacy_folder

        return LOG_FOLDER

    def populate_items_from_session(self):
        self.items_table.blockSignals(True)
        self.items_table.setRowCount(0)

        for item in self.session.items:
            row = self.items_table.rowCount()
            self.items_table.insertRow(row)
            self.items_table.setItem(row, 0, QTableWidgetItem(item.name))
            self.items_table.setItem(row, 1, QTableWidgetItem(item.description))

        self.items_table.blockSignals(False)

    def populate_captured_weights_from_session(self):
        self.captured_table.setRowCount(0)

        for item_index in sorted(self.session.item_results):
            result = self.session.item_results[item_index]
            readings = result["readings"]
            statuses = rank_weight_statuses(readings)

            for weight_number, (reading, status) in enumerate(
                zip(readings, statuses),
                start=1,
            ):
                self.add_captured_row(item_index, weight_number, reading, status)

    def stop_logging(self):
        if self.reader:
            self.reader.stop()
            self.reader.wait(2500)
            self.reader = None
        self.set_setup_enabled(True)
        self.set_logging_enabled(False)
        self.log("Stopped.")

    def on_serial_error(self, message):
        detail = message
        if "ACCESS IS DENIED" in caps(message):
            detail += (
                "\n\nCOM Port Is Already In Use. Close receive_test.py, "
                "Any Scale/Terminal Software, Or Another Copy Of This App, Then Try Again."
            )

        QMessageBox.critical(self, "Serial Error", detail)
        self.log(f"SERIAL ERROR: {message}")
        self.stop_logging()

    def on_reading(self, reading):
        self.latest_reading = reading
        self.live_label.setText(QcWorkbookSession.format_weight(reading))

    def on_raw_line(self, line):
        self.latest_raw_line = line
        self.raw_line_label.setText(f"Raw Serial: {line}")

    def capture_weight(self):
        if not self.session or not self.latest_reading:
            message = "Wait For A Scale Reading First."
            if self.latest_raw_line:
                message += f"\n\nLast Raw Serial Line:\n{self.latest_raw_line}"
                message += (
                    "\n\nThe App Is Connected, But It Has Not Received "
                    "A Numeric Weight Line Yet."
                )
            else:
                message += "\n\nNo Raw Serial Data Has Been Received Yet."
            QMessageBox.warning(self, "No Reading", message)
            return

        if is_zero(self.latest_reading["weight"]):
            QMessageBox.warning(self, "Zero Reading", "Place Weight On Scale Before Capturing.")
            return

        reading = dict(self.latest_reading)
        raw_row = self.session.record_reading(
            self.current_item_index,
            self.current_weight_number,
            reading,
        )
        self.current_readings.append(reading)
        self.current_raw_rows.append(raw_row)
        self.log(
            f"CAPTURED ITEM {self.current_item_index + 1} "
            f"WEIGHT {self.current_weight_number}: "
            f"{QcWorkbookSession.format_weight(reading)}"
        )
        self.add_captured_row(
            self.current_item_index,
            self.current_weight_number,
            reading,
            "",
        )
        self.latest_reading = None
        self.live_label.setText("Waiting For Next Scale Reading")

        if self.current_weight_number < WEIGHTS_PER_ITEM:
            self.current_weight_number += 1
            self.update_target()
            return

        statuses = self.session.finalize_item(
            self.current_item_index,
            self.current_readings,
            self.current_raw_rows,
        )
        self.update_item_status_rows(self.current_item_index, statuses)
        self.log(f"SAVED ITEM {self.current_item_index + 1}: {', '.join(statuses)}")
        if self.continue_single_item:
            self.continue_single_item = False
            self.current_readings = []
            self.current_raw_rows = []
            self.log(f"FINISHED CONTINUING ITEM {self.current_item_index + 1}.")
            QMessageBox.information(self, "Item Complete", "Select Another Item To Continue.")
            self.stop_logging()
            return

        self.current_item_index += 1
        self.current_weight_number = 1
        self.current_readings = []
        self.current_raw_rows = []

        if self.current_item_index >= len(self.session.items):
            self.log(f"COMPLETED ALL ITEMS: {self.session.filename}")
            QMessageBox.information(self, "Complete", "All Items Have Been Recorded.")
            self.stop_logging()
        else:
            self.update_target()

    def update_target(self):
        if not self.session or self.current_item_index >= len(self.session.items):
            self.target_label.setText("Complete.")
            return

        item = self.session.items[self.current_item_index]
        self.target_label.setText(
            f"ITEM {self.current_item_index + 1}: {item.name} | "
            f"WEIGHT {self.current_weight_number} OF {WEIGHTS_PER_ITEM}"
        )

    def set_setup_enabled(self, enabled):
        for widget in (
            self.project_edit,
            self.port_combo,
            self.baud_spin,
            self.dtr_check,
            self.rts_check,
            self.item_edit,
            self.description_edit,
            self.add_item_button,
            self.remove_item_button,
            self.start_button,
        ):
            widget.setEnabled(enabled)

        self.items_table.setEnabled(True)
        self.edit_item_button.setEnabled(True)
        self.continue_item_button.setEnabled(self.session is not None and enabled)

    def set_logging_enabled(self, enabled):
        self.capture_button.setEnabled(enabled)
        self.request_weight_button.setEnabled(enabled)
        self.edit_weight_button.setEnabled(enabled)
        self.stop_button.setEnabled(enabled)
        if enabled:
            self.continue_item_button.setEnabled(False)
        else:
            self.continue_item_button.setEnabled(self.session is not None)

    def request_weight(self):
        if not self.reader:
            QMessageBox.warning(self, "Not Connected", "Start Logging Before Requesting Weight.")
            return

        self.reader.request_weight()
        self.log("Requested Weight From Scale.")

    def add_captured_row(self, item_index, weight_number, reading, status):
        row = self.captured_table.rowCount()
        self.captured_table.insertRow(row)

        values = [
            self.session.items[item_index].name,
            str(weight_number),
            f"{reading['weight']:.3f}",
            caps(reading["unit"]),
            status,
        ]

        for column, value in enumerate(values):
            table_item = QTableWidgetItem(value)
            table_item.setData(Qt.UserRole, (item_index, weight_number))
            self.captured_table.setItem(row, column, table_item)

    def update_item_status_rows(self, _item_index, _statuses):
        self.populate_captured_weights_from_session()

    def refresh_captured_item_names(self, item_index):
        if not self.session:
            return

        item_name = self.session.items[item_index].name
        for row in range(self.captured_table.rowCount()):
            row_item = self.captured_table.item(row, 0)
            if row_item is None:
                continue

            stored_item_index, _weight_number = row_item.data(Qt.UserRole)
            if stored_item_index == item_index:
                row_item.setText(item_name)

    def remove_captured_rows_for_item(self, item_index):
        for row in range(self.captured_table.rowCount() - 1, -1, -1):
            row_item = self.captured_table.item(row, 0)
            if row_item is None:
                continue

            stored_item_index, _weight_number = row_item.data(Qt.UserRole)
            if stored_item_index == item_index:
                self.captured_table.removeRow(row)

    def edit_selected_weight(self):
        if not self.session:
            return

        selected_rows = sorted({index.row() for index in self.captured_table.selectedIndexes()})
        if not selected_rows:
            QMessageBox.warning(self, "No Weight Selected", "Select A Captured Weight To Edit.")
            return

        row = selected_rows[0]
        row_item = self.captured_table.item(row, 0)
        if row_item is None:
            return

        item_index, weight_number = row_item.data(Qt.UserRole)
        if item_index not in self.session.item_results:
            QMessageBox.warning(
                self,
                "Item Not Complete",
                "Finish All Three Weights For This Item Before Editing.",
            )
            return

        reading = self.session.item_results[item_index]["readings"][weight_number - 1]
        new_weight, ok = QInputDialog.getDouble(
            self,
            "Edit Weight",
            "Weight:",
            float(reading["weight"]),
            -999999.0,
            999999.0,
            3,
        )
        if not ok:
            return

        unit, ok = QInputDialog.getText(
            self,
            "Edit Unit",
            "Unit:",
            text=caps(reading.get("unit", "")),
        )
        if not ok:
            return

        statuses = self.session.update_reading(
            item_index,
            weight_number,
            new_weight,
            caps(unit.strip()),
        )
        self.update_item_status_rows(item_index, statuses)
        self.log(
            f"UPDATED ITEM {item_index + 1} WEIGHT {weight_number}: "
            f"{new_weight:.3f} {caps(unit)}"
        )

    def open_logs_folder(self):
        LOG_FOLDER.mkdir(exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOG_FOLDER)))

    def run_com_port_test(self):
        ports = list(list_ports.comports())
        lines = ["Available COM Ports:"]

        if ports:
            lines.extend(f"{port.device} - {port.description}" for port in ports)
        else:
            lines.append("No COM Ports Found.")

        message = "\n".join(lines)
        QMessageBox.information(self, "Com Port Test", message)
        self.log("Com Port Test Ran.")

    def run_receive_test(self):
        if self.reader:
            QMessageBox.warning(
                self,
                "Receive Test",
                "Stop Logging Before Running Receive Test. The Scale Port Can Only Be Opened Once.",
            )
            return

        message, detected_port = self.receive_test_output()
        if detected_port:
            self.load_ports()
            self.port_combo.setCurrentText(detected_port)
            self.update_serial_settings_label()
            message += f"\n\nGUI Port Updated To {detected_port}."

        QMessageBox.information(self, "Receive Test", message)
        self.log("Receive Test Ran.")

    def receive_test_output(self):
        ports = list(list_ports.comports())
        lines = ["Available COM Ports:"]
        first_open_port = None
        detected_port = None

        if not ports:
            return "No COM Ports Found.", None

        lines.extend(f"{port.device} - {port.description}" for port in ports)
        lines.append("")
        lines.append("Probing COM Ports For Scale Data...")
        lines.append("")

        for port in ports:
            lines.append(f"Trying {port.device}...")

            try:
                with serial.Serial(
                    port=port.device,
                    baudrate=self.baud_spin.value(),
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=1,
                    xonxoff=False,
                    rtscts=False,
                    dsrdtr=False,
                ) as scale:
                    scale.dtr = self.dtr_check.isChecked()
                    scale.rts = self.rts_check.isChecked()
                    scale.reset_input_buffer()

                    if first_open_port is None:
                        first_open_port = port.device

                    deadline = time.time() + 2
                    while time.time() < deadline:
                        raw = scale.readline()
                        if not raw:
                            continue

                        line = clean_scale_line(raw.decode("ascii", errors="ignore"))
                        if line:
                            lines.append(f"Raw: {line}")
                            lines.append(f"Detected Data On {port.device}: {line}")
                            detected_port = port.device
                            return "\n".join(lines), detected_port

            except serial.SerialException as exc:
                lines.append(f"Could Not Open {port.device}: {exc}")

        if first_open_port:
            lines.append(f"No Data Detected. Using First Open Port: {first_open_port}")
            return "\n".join(lines), first_open_port

        lines.append("No Usable COM Port Found.")
        return "\n".join(lines), None

    @staticmethod
    def detect_port_from_receive_test_output(output):
        patterns = (
            r"DETECTED DATA ON\s+(COM\d+)",
            r"CONNECTED TO\s+(COM\d+)",
            r"USING FIRST OPEN PORT:\s+(COM\d+)",
            r"AVAILABLE COM PORTS:\s*(COM\d+)",
        )

        upper_output = caps(output)
        for pattern in patterns:
            match = re.search(pattern, upper_output)
            if match:
                return match.group(1)

        return None

    def log(self, message):
        self.status_box.append(str(message))

    def closeEvent(self, event):
        self.stop_logging()
        event.accept()


def run():
    app = QApplication(sys.argv)
    app.setOrganizationName("Gregory")
    app.setApplicationName("PY 232 Scale")
    app.setProperty("defaultStyleName", app.style().objectName())
    app.setProperty("defaultPalette", QPalette(app.palette()))
    apply_theme(str(QSettings().value("theme", "system")))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
