@echo off
chcp 65001 > nul
title qcatch - タスク追加
cd /d "%~dp0"
python qcatch.py prompt
