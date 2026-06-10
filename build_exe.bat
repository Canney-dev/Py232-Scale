@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt
python -m pip install -r requirements-build.txt
python -m PyInstaller --clean --noconfirm py232_scale.spec
python -m PyInstaller --clean --noconfirm py232_scale_onefile.spec
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path 'dist\PY_232_Scale_Windows.zip') { Remove-Item 'dist\PY_232_Scale_Windows.zip' -Force }; Compress-Archive -Path 'dist\PY 232 Scale' -DestinationPath 'dist\PY_232_Scale_Windows.zip' -Force"
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path 'dist\PY_232_Scale_OneFile_Windows.zip') { Remove-Item 'dist\PY_232_Scale_OneFile_Windows.zip' -Force }; Compress-Archive -Path 'dist\PY 232 Scale.exe' -DestinationPath 'dist\PY_232_Scale_OneFile_Windows.zip' -Force"
pause
