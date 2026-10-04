"""Pruebas automatizadas de la logica de NET AGENT 0.1."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from netagent import (  # noqa: E402
    ESTADO_FALLO,
    ESTADO_INICIAL,
    ESTADO_OK,
    ErrorValidacion,
    agregar_conexion,
    agregar_equipo,
    comprobar_red,
    connect,
    generar_mapa_dot,
    listar_conexiones,
    listar_equipos,
    listar_revisiones,
    resultados_de_revision,
    validar_ipv4,
)


class PruebasNetAgent(unittest.TestCase):
    def setUp(self):
        self.carpeta = tempfile.TemporaryDirectory()
        self.db = connect(Path(self.carpeta.name) / "prueba.sqlite3")

    def tearDown(self):
        self.db.close()
        self.carpeta.cleanup()

    def test_connect_crea_las_cuatro_tablas(self):
        tablas = [
            r[0]
            for r in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type = ? ORDER BY name",
                ("table",),
            )
        ]
        self.assertEqual(tablas, ["conexiones", "equipos", "resultados", "revisiones"])

    def test_validacion_de_ipv4(self):
        self.assertEqual(validar_ipv4(" 127.0.0.1 "), "127.0.0.1")
        for invalida in ("", "abc", "256.1.1.1", "192.168.1", "0.0.0.0", "::1"):
            with self.assertRaises(ErrorValidacion):
                validar_ipv4(invalida)

    def test_equipo_nuevo_queda_sin_comprobar_y_no_se_duplica(self):
        agregar_equipo(self.db, "Mi-PC", "PC", "127.0.0.1", "Prueba local")
        equipo = listar_equipos(self.db)[0]
        self.assertEqual(equipo["estado"], ESTADO_INICIAL)
        with self.assertRaises(ErrorValidacion):
            agregar_equipo(self.db, "Mi-PC", "PC", "127.0.0.2")
        with self.assertRaises(ErrorValidacion):
            agregar_equipo(self.db, "Otra", "PC", "127.0.0.1")

    def test_conexiones_y_mapa(self):
        a = agregar_equipo(self.db, "A", "PC", "10.0.0.1")
        b = agregar_equipo(self.db, "B", "Switch", "10.0.0.2")
        with self.assertRaises(ErrorValidacion):
            agregar_conexion(self.db, a, a)
        agregar_conexion(self.db, a, b, "Cable UTP")
        with self.assertRaises(ErrorValidacion):
            agregar_conexion(self.db, b, a)  # misma conexion en sentido inverso
        self.assertEqual(len(listar_conexiones(self.db)), 1)
        dot = generar_mapa_dot(self.db)
        self.assertIn("graph red", dot)
        self.assertIn("--", dot)

    def test_comprobar_red_guarda_estado_e_historial(self):
        agregar_equipo(self.db, "Arriba", "PC", "10.0.0.1")
        agregar_equipo(self.db, "Abajo", "PC", "10.0.0.2")

        def ping_falso(ip):
            return (ip == "10.0.0.1"), f"salida de {ip}"

        revision_id = comprobar_red(self.db, ping=ping_falso)
        estados = {e["nombre"]: e["estado"] for e in listar_equipos(self.db)}
        self.assertEqual(estados, {"Arriba": ESTADO_OK, "Abajo": ESTADO_FALLO})
        revision = listar_revisiones(self.db)[0]
        self.assertEqual((revision["total"], revision["respondieron"]), (2, 1))
        self.assertEqual(len(resultados_de_revision(self.db, revision_id)), 2)


if __name__ == "__main__":
    unittest.main()
