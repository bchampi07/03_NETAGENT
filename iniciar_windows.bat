@echo off
rem NET AGENT 0.1 - instalacion y ejecucion en Windows 10/11
cd /d "%~dp0"

rem Preferir el lanzador "py" de python.org; si no existe, usar "python".
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo No se encontro Python. Instale Python 3.10 o superior desde python.org
    echo y marque la opcion "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno virtual...
    %PY% -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
    echo No se pudo crear el entorno virtual con "%PY%".
    echo Instale Python desde python.org y vuelva a intentarlo.
    goto error
)

echo Instalando dependencias...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error

echo Iniciando NET AGENT en http://127.0.0.1:8501 (Ctrl+C para detener)
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
goto fin

:error
echo Ocurrio un error durante la instalacion.
pause
exit /b 1

:fin
pause
