@echo off
echo Building Komet Americano Desktop App...
echo.
echo Step 1: Installing dependencies...
pip install -r requirements-desktop.txt
echo.
echo Step 2: Building executable...
pyinstaller desktop.spec --clean
echo.
echo Done! Find KometAmericano.exe in the dist/ folder.
pause
