# NET AGENT 0.1

## Descripción

NET AGENT es una aplicación web local para registrar los equipos de una red,
dibujar un mapa con sus conexiones y comprobar su conectividad mediante `ping`.
Guarda el inventario y el historial de revisiones en una base de datos SQLite
local. Debe usarse únicamente en redes y equipos autorizados.

## Integrantes

| N.º | Apellidos y nombres |
|-----|---------------------|
| 1   | _AITA CANSAYA JOSE ANDRES_         |
| 2   | _ALVAREZ BARRIGA SEBASTIAN ANTONIO_         |
| 3   | _CHAMPI HUAMANI BRALY CARLO ANDRE_         |
| 4   | _HURTADO RAMOS SERGIO ADRIANO_         |
| 5   | _VALVERDE REY MILWARD JOAQUIN_         |


## Tecnologías utilizadas

- Python 3.10 o superior
- Streamlit (interfaz web)
- SQLite (base de datos local, incluida en Python)
- Comando `ping` del sistema operativo

## Requisitos

- Windows 10 u 11
- Python 3.10 o superior, con la opción *Add Python to PATH* activada
- Navegador web
- Git (opcional, solo para clonar el repositorio)

Dependencias del proyecto: ver `requirements.txt` (`streamlit>=1.64,<2`).
NET AGENT no usa variables de entorno ni archivo `.env`.

## Instalación y ejecución

1. Descargue el repositorio (*Code → Download ZIP*) y extráigalo, o clónelo:

   ```
   git clone https://github.com/bchampi07/03_NETAGENT.git
   cd 03_NETAGENT
   ```

2. Desde CMD, en la carpeta que contiene `app.py` y `requirements.txt`:

   ```
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   .venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
   ```

3. Abra <http://127.0.0.1:8501> en el navegador.

Alternativa rápida: haga doble clic en `iniciar_windows.bat`.

La base de datos (`datos/net_agent.sqlite3`) se crea automáticamente la primera vez.
Para detener la aplicación, pulse `Ctrl+C` en la ventana de CMD.

## Pruebas automáticas

```
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Estructura del repositorio

| Archivo | Contenido |
|---------|-----------|
| `app.py` | Interfaz web con Streamlit |
| `netagent.py` | Validación, almacenamiento SQLite, mapa y comprobaciones ping |
| `requirements.txt` | Dependencias |
| `iniciar_windows.bat` | Instalación y ejecución en Windows |
| `tests/test_netagent.py` | Pruebas automatizadas |
| `.gitignore` | Exclusión del entorno virtual, la base de datos local y configuración sensible |
