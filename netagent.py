"""NET AGENT 0.1 - logica del sistema.

Contiene la validacion de datos, el almacenamiento en SQLite, la generacion
del mapa de red y las comprobaciones de conectividad mediante ping.
La interfaz web (Streamlit) se encuentra en app.py.
"""

from __future__ import annotations

import ipaddress
import platform
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "datos" / "net_agent.sqlite3"

TIPOS_EQUIPO = (
    "PC",
    "Laptop",
    "Servidor",
    "Router",
    "Switch",
    "Firewall",
    "Impresora",
    "Otro",
)

ESTADO_INICIAL = "Sin comprobar"
ESTADO_OK = "Responde"
ESTADO_FALLO = "No responde"

SCHEMA = """
CREATE TABLE IF NOT EXISTS equipos (
    id             INTEGER PRIMARY KEY,
    nombre         TEXT NOT NULL UNIQUE,
    tipo           TEXT NOT NULL,
    ipv4           TEXT NOT NULL UNIQUE,
    area           TEXT NOT NULL DEFAULT '',
    estado         TEXT NOT NULL DEFAULT 'Sin comprobar',
    ultima_revision TEXT
);

CREATE TABLE IF NOT EXISTS conexiones (
    id            INTEGER PRIMARY KEY,
    equipo_a_id   INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
    equipo_b_id   INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,
    descripcion   TEXT NOT NULL DEFAULT '',
    UNIQUE (equipo_a_id, equipo_b_id),
    CHECK (equipo_a_id < equipo_b_id)
);

CREATE TABLE IF NOT EXISTS revisiones (
    id            INTEGER PRIMARY KEY,
    fecha         TEXT NOT NULL,
    total         INTEGER NOT NULL,
    respondieron  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS resultados (
    id            INTEGER PRIMARY KEY,
    revision_id   INTEGER NOT NULL REFERENCES revisiones(id) ON DELETE CASCADE,
    equipo_id     INTEGER REFERENCES equipos(id) ON DELETE SET NULL,
    nombre        TEXT NOT NULL,
    ipv4          TEXT NOT NULL,
    estado        TEXT NOT NULL,
    salida        TEXT NOT NULL DEFAULT '',
    fecha         TEXT NOT NULL
);
"""


class ErrorValidacion(ValueError):
    """Error de validacion con un mensaje comprensible para el usuario."""


# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------

def connect(path=None) -> sqlite3.Connection:
    """Abre la base de datos SQLite y crea las tablas si no existen."""
    if path is not None and str(path) == ":memory:":
        db = sqlite3.connect(":memory:")
    else:
        ruta = Path(path) if path is not None else DEFAULT_DB
        ruta.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(ruta)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA)
    db.commit()
    return db


def _ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Validacion
# ---------------------------------------------------------------------------

def validar_ipv4(texto: str) -> str:
    """Devuelve la IPv4 normalizada o lanza ErrorValidacion."""
    try:
        ip = ipaddress.IPv4Address((texto or "").strip())
    except ValueError:
        raise ErrorValidacion(
            "La direccion IPv4 no es valida. Use el formato 192.168.1.10."
        ) from None
    if ip.is_unspecified or ip.is_multicast:
        raise ErrorValidacion("La direccion IPv4 no corresponde a un equipo.")
    return str(ip)


def validar_equipo(nombre: str, tipo: str, ipv4: str, area: str) -> dict:
    """Valida y normaliza los datos de un equipo."""
    nombre = (nombre or "").strip()
    area = (area or "").strip()
    if not nombre:
        raise ErrorValidacion("El nombre del equipo es obligatorio.")
    if len(nombre) > 50:
        raise ErrorValidacion("El nombre no debe superar 50 caracteres.")
    if len(area) > 80:
        raise ErrorValidacion("El area no debe superar 80 caracteres.")
    if tipo not in TIPOS_EQUIPO:
        raise ErrorValidacion("El tipo de equipo no es valido.")
    return {
        "nombre": nombre,
        "tipo": tipo,
        "ipv4": validar_ipv4(ipv4),
        "area": area,
    }


# ---------------------------------------------------------------------------
# Equipos
# ---------------------------------------------------------------------------

def agregar_equipo(db, nombre, tipo, ipv4, area="") -> int:
    datos = validar_equipo(nombre, tipo, ipv4, area)
    try:
        cur = db.execute(
            "INSERT INTO equipos (nombre, tipo, ipv4, area, estado) "
            "VALUES (?, ?, ?, ?, ?)",
            (datos["nombre"], datos["tipo"], datos["ipv4"], datos["area"],
             ESTADO_INICIAL),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        raise ErrorValidacion(
            "Ya existe un equipo con ese nombre o con esa direccion IPv4."
        ) from None
    return cur.lastrowid


def listar_equipos(db) -> list:
    return db.execute("SELECT * FROM equipos ORDER BY nombre").fetchall()


def eliminar_equipo(db, equipo_id: int) -> None:
    db.execute("DELETE FROM equipos WHERE id = ?", (equipo_id,))
    db.commit()


# ---------------------------------------------------------------------------
# Conexiones y mapa
# ---------------------------------------------------------------------------

def agregar_conexion(db, equipo_1: int, equipo_2: int, descripcion="") -> int:
    if equipo_1 == equipo_2:
        raise ErrorValidacion("Un equipo no puede conectarse consigo mismo.")
    a, b = sorted((int(equipo_1), int(equipo_2)))
    existentes = {r["id"] for r in db.execute("SELECT id FROM equipos")}
    if a not in existentes or b not in existentes:
        raise ErrorValidacion("Alguno de los equipos seleccionados no existe.")
    try:
        cur = db.execute(
            "INSERT INTO conexiones (equipo_a_id, equipo_b_id, descripcion) "
            "VALUES (?, ?, ?)",
            (a, b, (descripcion or "").strip()[:100]),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        raise ErrorValidacion("Esa conexion ya esta registrada.") from None
    return cur.lastrowid


def listar_conexiones(db) -> list:
    return db.execute(
        "SELECT c.id, c.descripcion, "
        "       a.nombre AS equipo_a, b.nombre AS equipo_b "
        "FROM conexiones c "
        "JOIN equipos a ON a.id = c.equipo_a_id "
        "JOIN equipos b ON b.id = c.equipo_b_id "
        "ORDER BY a.nombre, b.nombre"
    ).fetchall()


def eliminar_conexion(db, conexion_id: int) -> None:
    db.execute("DELETE FROM conexiones WHERE id = ?", (conexion_id,))
    db.commit()


def _dot(texto: str) -> str:
    return str(texto).replace("\\", "\\\\").replace('"', '\\"')


def generar_mapa_dot(db) -> str:
    """Genera el mapa de red en formato Graphviz DOT."""
    colores = {
        ESTADO_OK: "#b7e4c7",
        ESTADO_FALLO: "#f4a6a6",
        ESTADO_INICIAL: "#e0e0e0",
    }
    lineas = [
        "graph red {",
        "  rankdir=LR;",
        '  node [shape=box, style="rounded,filled", fontname="Arial"];',
    ]
    for e in listar_equipos(db):
        etiqueta = f"{_dot(e['nombre'])}\\n{e['tipo']}\\n{e['ipv4']}"
        color = colores.get(e["estado"], "#e0e0e0")
        lineas.append(
            f'  "n{e["id"]}" [label="{etiqueta}", fillcolor="{color}"];'
        )
    for c in db.execute(
        "SELECT equipo_a_id, equipo_b_id, descripcion FROM conexiones"
    ):
        etiqueta = f' [label="{_dot(c["descripcion"])}"]' if c["descripcion"] else ""
        lineas.append(f'  "n{c["equipo_a_id"]}" -- "n{c["equipo_b_id"]}"{etiqueta};')
    lineas.append("}")
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Comprobacion de red (ping)
# ---------------------------------------------------------------------------

def _decodificar(datos: bytes) -> str:
    for codificacion in ("utf-8", "cp850", "latin-1"):
        try:
            return datos.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return datos.decode("utf-8", errors="replace")


def hacer_ping(ipv4: str, timeout_ms: int = 2000) -> tuple:
    """Envia un ping a la IPv4 indicada. Devuelve (responde, salida)."""
    ip = validar_ipv4(ipv4)
    es_windows = platform.system().lower() == "windows"
    if es_windows:
        comando = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
    else:
        comando = ["ping", "-c", "1", "-W", str(max(1, timeout_ms // 1000)), ip]
    try:
        r = subprocess.run(
            comando, capture_output=True, timeout=timeout_ms / 1000 + 5
        )
    except FileNotFoundError:
        return False, "No se encontro el comando ping en este equipo."
    except subprocess.TimeoutExpired:
        return False, "Tiempo de espera agotado."
    salida = (_decodificar(r.stdout) + _decodificar(r.stderr)).strip()
    responde = r.returncode == 0
    if es_windows:
        # En Windows, "host de destino inaccesible" tambien devuelve codigo 0.
        responde = responde and "ttl=" in salida.lower()
    return responde, salida


def comprobar_red(db, ping=hacer_ping) -> int:
    """Comprueba todos los equipos registrados y guarda la revision."""
    equipos = listar_equipos(db)
    if not equipos:
        raise ErrorValidacion("Registre al menos un equipo antes de comprobar la red.")
    fecha = _ahora()
    revision_id = db.execute(
        "INSERT INTO revisiones (fecha, total, respondieron) VALUES (?, ?, 0)",
        (fecha, len(equipos)),
    ).lastrowid
    respondieron = 0
    for e in equipos:
        responde, salida = ping(e["ipv4"])
        estado = ESTADO_OK if responde else ESTADO_FALLO
        respondieron += 1 if responde else 0
        db.execute(
            "UPDATE equipos SET estado = ?, ultima_revision = ? WHERE id = ?",
            (estado, fecha, e["id"]),
        )
        db.execute(
            "INSERT INTO resultados "
            "(revision_id, equipo_id, nombre, ipv4, estado, salida, fecha) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (revision_id, e["id"], e["nombre"], e["ipv4"], estado, salida, fecha),
        )
    db.execute(
        "UPDATE revisiones SET respondieron = ? WHERE id = ?",
        (respondieron, revision_id),
    )
    db.commit()
    return revision_id


# ---------------------------------------------------------------------------
# Historial
# ---------------------------------------------------------------------------

def listar_revisiones(db) -> list:
    return db.execute("SELECT * FROM revisiones ORDER BY id DESC").fetchall()


def resultados_de_revision(db, revision_id: int) -> list:
    return db.execute(
        "SELECT * FROM resultados WHERE revision_id = ? ORDER BY nombre",
        (revision_id,),
    ).fetchall()
