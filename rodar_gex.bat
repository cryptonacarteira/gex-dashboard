@echo off
rem Roda localmente: baixa os dados e gera os dashboards
cd /d "%~dp0"
python baixar_dados.py || exit /b 1
python gex.py || exit /b 1
python historico.py || exit /b 1
python dashboard_historico.py