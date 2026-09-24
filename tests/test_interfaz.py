import json
import unittest
from datetime import date

from horarios import BASE, selecciones_del_area
from interfaz import guardar_persona, lunes_del_mes


class InterfazTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((BASE / "configuracion.json").read_text(encoding="utf-8"))

    def test_editar_semana_compartida_y_renombrar(self):
        nuevo = guardar_persona(self.config, "Cocina", "Ana", "Andrea", "sábado", 1,
                                date(2026, 10, 1), ["T"] * 5)
        area = nuevo["areas"]["Cocina"]
        seleccion = selecciones_del_area("Cocina", area, nuevo["turnos"])
        self.assertEqual(seleccion["2026-09-28"]["Andrea"], "T")
        self.assertEqual(area["turnos_por_mes"]["2026-09"]["Andrea"][-1], "T")
        self.assertNotIn("Ana", area["dias_libres"])
        self.assertEqual(area["domingo_grupo"]["Andrea"], 1)
        self.assertEqual(area["domingo_grupo"]["Luis"], 1)
        self.assertIn("Ana", self.config["areas"]["Cocina"]["empleados"])

    def test_automatico_preserva_otras_semanas(self):
        nuevo = guardar_persona(self.config, "Cocina", "Ana", "Ana", "lunes", 0,
                                date(2026, 10, 1), [None] * 5)
        area = nuevo["areas"]["Cocina"]
        seleccion = selecciones_del_area("Cocina", area, nuevo["turnos"])
        self.assertNotIn("Ana", seleccion.get("2026-09-28", {}))
        self.assertEqual(seleccion["2026-09-21"]["Ana"], "T")
        self.assertEqual(seleccion["2026-08-31"]["Ana"], "M")

    def test_nombre_repetido_no_modifica_configuracion(self):
        with self.assertRaises(ValueError):
            guardar_persona(self.config, "Cocina", "Ana", "Luis", "lunes", 0,
                            date(2026, 9, 1), ["M"] * 5)
        self.assertIn("Ana", self.config["areas"]["Cocina"]["empleados"])

    def test_seis_semanas(self):
        semanas = lunes_del_mes(date(2026, 3, 1))
        self.assertEqual(len(semanas), 6)
        self.assertEqual(semanas[0], date(2026, 2, 23))


if __name__ == "__main__":
    unittest.main()
