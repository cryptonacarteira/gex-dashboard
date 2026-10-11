@echo off
rem Roda localmente: baixa os dados SPX e gera o dashboard
cd /d "%~dp0"
python baixar_spx.py || exit /b 1
python gex.py