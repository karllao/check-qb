@echo off
echo 当前盘符和路径：%~dp0
echo 当前盘符：%~d0
cd %~d0
cd %~dp0
python crontab.py
