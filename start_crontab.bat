@echo off
echo ��ǰ�̷���·����%~dp0
echo ��ǰ�̷���%~d0
cd %~d0
cd %~dp0
python crontab.py
