# PY 232 Scale

PySide6 desktop app for recording three scale readings per item and saving a printable Excel QC checklist.

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
