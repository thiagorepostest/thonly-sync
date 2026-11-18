@echo off
title Thonly Lyric Studio (Local)
if not exist .venv (
  echo Criando ambiente virtual Python...
  python -m venv .venv
)
call .venv\Scripts\activate
pip install -q -r requirements.txt
echo Iniciando Thonly Lyric Studio em http://localhost:8000 ...
python server.py
pause
