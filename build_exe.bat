@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt
python -m pip install -r requirements-build.txt
python -m PyInstaller --clean --noconfirm py232_scale.spec
python -m PyInstaller --clean --noconfirm py232_scale_onefile.spec
pause
