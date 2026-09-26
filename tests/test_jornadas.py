import copy
import unittest
from datetime import date, timedelta

from horarios import generar, generar_mes, evaluar_cobertura
from interfaz import guardar_persona


class JornadasTest(unittest.TestCase):
    def setUp(self):
        area = {"empleados": ["A", "B", "C", "D"],
                "dias_libres": {"A": "lunes", "B": "martes", "C": "miércoles", "D": "jueves"},
                "cobertura": {"M": 1, "T": 1}}
        self.config = {"empresa": "Prueba", "inicio_rotacion": "2026-09-28",
                       "turnos": {"M": "Mañana · 09:00 a 17:00", "T": "Tarde · 16:00 a 00:00"},
                       "areas": {a: copy.deepcopy(area) for a in ("Cocina", "Barra", "Garzones")}}
        self.inicio = date(2026, 9, 28)

    def agregar(self, jornada):
        self.config = guardar_persona(self.config, "Cocina", None, "PT", "lunes", 0,
                                      self.inicio, ["M"]*5, jornada=jornada)

    def test_pt30_cuatro_dias_sin_descuentos(self):
        self.agregar({"tipo": "part_time_30", "dias": [0, 2, 5, 6]})
        fechas, resultado = generar(self.config, self.inicio, 3)
        turnos = resultado["Cocina"]["PT"]
        for i, dia in enumerate(fechas):
            self.assertEqual(turnos[i] == "LIBRE", dia.weekday() not in (0, 2, 5, 6))
            self.assertFalse(turnos[i].reducido)
            self.assertEqual(turnos[i].horas_semana, 32)
        self.assertEqual(turnos[6].minutos, 480)
        self.assertEqual(turnos[13].minutos, 480)

    def test_pt20_dos_dias_y_cruce_medianoche(self):
        self.agregar({"tipo": "part_time_20", "dias": [5, 6], "entradas": {"5": "20:00", "6": "10:30"}})
        fechas, resultado = generar(self.config, self.inicio, 3)
        turnos = resultado["Cocina"]["PT"]
        for i, dia in enumerate(fechas):
            self.assertEqual(turnos[i].minutos, 630 if dia.weekday() in (5, 6) else 0)
            self.assertEqual(turnos[i].horas_semana, 21)
            self.assertFalse(turnos[i].reducido)
        self.assertIn("20:00 a 06:30", turnos[5].descripcion)
        self.assertIn("10:30 a 21:00", turnos[6].descripcion)
        _, octubre = generar_mes(self.config, date(2026, 10, 1))
        self.assertEqual([t.descripcion for t in octubre["Cocina"]["PT"][:18]],
                         [t.descripcion for t in turnos[3:]])
        evaluar_cobertura(self.config, date(2026, 10, 1))

    def test_pt30_rechaza_mas_de_32(self):
        self.agregar({"tipo": "part_time_30", "dias": [0, 1, 2, 3]})
        self.config["turnos"]["X"] = "Largo · 09:00 a 19:00"
        self.config["areas"]["Cocina"]["turnos_semanales"]["2026-09-28"]["PT"] = "X"
        with self.assertRaisesRegex(ValueError, "máximo es 32"):
            generar(self.config, self.inicio, 1)

    def test_validacion_dias_y_entradas(self):
        for jornada in ({"tipo": "part_time_30", "dias": [0, 1, 2]},
                        {"tipo": "part_time_20", "dias": [5, 5], "entradas": {"5": "09:00"}},
                        {"tipo": "part_time_20", "dias": [5, 6], "entradas": {"5": "25:00", "6": "09:00"}}):
            with self.subTest(jornada=jornada):
                with self.assertRaises(ValueError):
                    self.agregar(jornada)

    def test_renombrar_y_volver_a_full_time(self):
        self.agregar({"tipo": "part_time_30", "dias": [0, 2, 5, 6]})
        nuevo = guardar_persona(self.config, "Cocina", "PT", "Renombrado", "martes", 1,
                                self.inicio, ["M"]*5)
        self.assertNotIn("PT", nuevo["areas"]["Cocina"]["jornadas"])
        self.assertEqual(nuevo["areas"]["Cocina"]["jornadas"]["Renombrado"]["tipo"], "part_time_30")
        nuevo = guardar_persona(nuevo, "Cocina", "Renombrado", "Renombrado", "martes", 1,
                                self.inicio, ["M"]*5, jornada={"tipo": "full_time"})
        self.assertEqual(nuevo["areas"]["Cocina"]["dias_libres"]["Renombrado"], "martes")
        generar(nuevo, self.inicio, 1)


if __name__ == "__main__":
    unittest.main()
