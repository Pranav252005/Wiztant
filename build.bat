@echo off
echo Building Whiztant...
pip install -r requirements.txt
pyinstaller whiztant.spec --clean
echo Done! Check the dist\ folder for Whiztant.exe
pause
