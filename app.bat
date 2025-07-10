@echo off
call .venv\Scripts\activate
python mysite\manage.py runserver 0.0.0.0:8000
