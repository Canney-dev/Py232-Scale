# PY 232 Scale

PySide6 desktop app for recording three scale readings per item and saving a printable Excel QC checklist.

![PY 232 Scale screenshot](docs/py-232-scale-screenshot.png)

## SETUP

```powershell
python -m pip install -r requirements.txt
```

Or double-click:

```text
setup.bat
```

## RUN

```powershell
python main.py
```

Or double-click:

```text
run.bat
```

## PACKAGE

Build a Windows app folder with PyInstaller:

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-build.txt
python -m PyInstaller --clean --noconfirm py232_scale.spec
```

Build a single-file Windows executable:

```powershell
python -m PyInstaller --clean --noconfirm py232_scale_onefile.spec
```

Or double-click:

```text
build_exe.bat
```

The packaged app folder is created at:

```text
dist\PY 232 Scale\PY 232 Scale.exe
```

The single-file executable is created at:

```text
dist\PY 232 Scale.exe
```

If you use the folder package or a zipped copy of it, click `Extract all` before
running the app. Running the folder package directly from Windows zip preview
can show a `Failed to load Python DLL` error because Windows extracts the `.exe`
without the required `_internal` folder.

## EDITING

- Use `FILE > OPEN LOG` to open a previously saved `.xlsx` log for editing.
- Use `FILE > SAVE LOG` to manually save the currently open log.
- Use `FILE > PRINT LOG` to send the currently open log to an available printer.
- Open a saved log, select an item row, then click `CONTINUE SELECTED ITEM` to capture three new weights for that item.
- Double-click an item row to edit the item or description.
- Select an item and click `EDIT SELECTED ITEM` for guided item/description correction.
- Item corrections update the Excel form, raw data, and LOW/HIGH summaries after logging starts.
- Select a captured weight and click `EDIT SELECTED WEIGHT` to correct it.
- Edited weights automatically update the LOW/HIGH markings and bottom summaries.

## OUTPUT

Logs are saved to the `Logs` folder as Excel workbooks named like:

```text
Weight_QC_Form 1.xlsx
```

## LICENSES

PY 232 Scale is licensed under the MIT License. Third party dependency license
information is listed in `THIRD_PARTY_NOTICES.md`.
