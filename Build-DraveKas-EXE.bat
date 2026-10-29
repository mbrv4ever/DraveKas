@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==== DraveKas - EXE bouwen ====
py -3.12 -c "import PyQt6.QtMultimedia, neuvoice, onnxruntime" || (echo FOUT: py -3.12 mist PyQt6/neuvoice/onnxruntime & pause & exit /b 1)
py -3.12 -m PyInstaller --noconfirm --clean --onedir --windowed --name DraveKas --icon assets\icon.ico ^
  --add-data "assets;assets" --hidden-import kas_data --hidden-import leon ^
  --collect-all neuvoice --collect-all onnxruntime --collect-data certifi ^
  --exclude-module torch --exclude-module torchvision --exclude-module torchaudio --exclude-module tensorflow ^
  --exclude-module transformers --exclude-module matplotlib --exclude-module pandas --exclude-module scipy ^
  --exclude-module PyQt6.QtWebEngineCore --exclude-module tkinter dravekas.py
if errorlevel 1 (echo FOUT: PyInstaller is mislukt & pause & exit /b 1)
if not exist "dist\DraveKas\DraveKas.exe" (echo FOUT: geen exe gemaakt & pause & exit /b 1)
xcopy /E /I /Y assets "dist\DraveKas\assets" >nul
echo.
echo KLAAR: dist\DraveKas\DraveKas.exe
pause
