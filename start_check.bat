@echo off
echo ��ǰ�̷���·����%~dp0
echo ��ǰ�̷���%~d0
cd %~d0
cd %~dp0
:abc
python run_check.py
ping -n 60 127.1 >nul 2>nul
echo =====================================================================
echo =====================================================================
goto abc