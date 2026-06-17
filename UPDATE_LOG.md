# Update Log

This log covers project changes from the past two weeks, June 1-17, 2026.

## June 17, 2026

- Built the single-file Windows executable as `PY 232 Scale v0.08.exe`.
- Smoke tested the v0.08 executable to confirm the app launches and closes cleanly.
- Created and pushed the `v0.08` Git tag.
- Published the GitHub release `PY 232 Scale v0.08`.
- Uploaded the release asset `PY.232.Scale.v0.08.exe`.
- Recorded the v0.08 release asset SHA256 checksum:
  `F8B9722B1CFE46CB5C8A900E7BC9BC686CE2F9E5DF3C0A6B5777572816399047`.

## June 15, 2026

- Sorted completed item weights from lowest to highest so the lowest value appears in Weight 1, the middle value appears in Weight 2, and the highest value appears in Weight 3.
- Kept the `Low` marker on the lowest recorded value and the `High` marker on the highest recorded value after sorting.
- Refreshed the captured weights table after completing or editing an item so the on-screen order matches the saved Excel workbook.

## June 11, 2026

- Added theme selection under Settings with `System Default`, `Light`, and `Dark` options.
- Saved the selected theme preference so the app remembers it between launches.
- Added dark and light theme screenshots to the README as clickable thumbnails.
- Added the tested scales list to the README:
  - UWE SEK-30K Checkweighing Scale
  - Brecknell Digital Counting & Coin Scale B140

## June 10, 2026

- Added the PySide6 desktop GUI and named the app `PY 232 Scale`.
- Added the main application entry point, package marker, run script, setup script, and Python requirements.
- Added the workbook and scale parsing core for reading serial scale output and writing Excel `.xlsx` logs.
- Added support for multiple items and descriptions.
- Added three captured weights per item.
- Added automatic `Low` and `High` marking based on the lowest and highest captured values.
- Omitted any `Good` marker for the remaining middle weight.
- Added editable item names, descriptions, and captured weights.
- Added the ability to open previously saved logs, edit them, and continue weighing a selected item.
- Added saved Excel log output in the `Logs` folder using the `Weight_QC_Form #.xlsx` naming pattern.
- Added a printable Weight QC Checklist workbook template.
- Adjusted the printed checklist layout to fit standard letter printer paper.
- Improved row height handling so multi-line item descriptions and weight cells are not cut off.
- Added bottom summary areas that list all marked `Low` and marked `High` fields.
- Added COM port test helper support.
- Added receive test helper support for detecting raw scale output and updating the selected COM port.
- Added serial settings for COM port, baud rate, DTR, and RTS in the Settings menu.
- Added user-facing descriptions for serial settings.
- Added available printer support from the File menu.
- Added Open and Save options under the File menu.
- Added Open Logs Folder support.
- Improved scale parsing for ticket-style output including `Net:` weight lines.
- Added handling for COM port access errors when another program is already using the port.
- Added the MIT license with Gregory as the copyright holder.
- Added third-party license notices for project dependencies.
- Added README instructions for setup, running from source, packaging, serial settings, logs, printing, and Windows SmartScreen unknown publisher warnings.
- Added the main README screenshot.
- Added PyInstaller packaging support.
- Added a single-file PyInstaller build option.
- Added `.gitignore` for generated files.
