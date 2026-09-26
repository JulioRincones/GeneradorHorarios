import unittest
from datetime import date

from horarios import AREAS, evaluar_cobertura


class CoberturaHorariaTest(unittest.TestCase):
    def config(self, entrada="09:00", salida="17:00", reduccion="salida"):
        return {
            "empresa": "Prueba", "inicio_rotacion": "2026-09-28",
            "turnos": {"N": f"Turno · {entrada} a {salida}"},
            "turnos_detalle": {"N": {"nombre": "Turno", "dias": [[entrada, salida] for _ in range(7)], "reduccion": reduccion}},
            "areas": {area: {
                "empleados": ["A", "B", "C", "D"],
                "dias_libres": {"A": "lunes", "B": "martes", "C": "lunes", "D": "martes"},
                "cobertura": {"N": 1},
            } for area in AREAS},
        }

    def test_reduccion_deja_hueco_y_correccion_lo_resuelve(self):
        config = self.config()
        alertas = evaluar_cobertura(config, date(2026, 9, 1))
        lunes = [a for a in alertas if a["area"] == "Cocina" and a["inicio"].date() == date(2026, 9, 28)]
        self.assertEqual(len(lunes), 1)
        self.assertEqual(lunes[0]["inicio"].strftime("%H:%M"), "16:00")
        self.assertEqual(lunes[0]["fin"].strftime("%H:%M"), "17:00")
        self.assertEqual(lunes[0]["presentes"], 0)
        config["areas"]["Cocina"]["dias_libres"]["A"] = "miércoles"
        corregidas = evaluar_cobertura(config, date(2026, 9, 1))
        self.assertFalse(any(a["area"] == "Cocina" and a["inicio"].date() == date(2026, 9, 28) for a in corregidas))

    def test_precision_media_hora(self):
        alertas = evaluar_cobertura(self.config("08:30", "16:30"), date(2026, 9, 1))
        a = next(a for a in alertas if a["inicio"].date() == date(2026, 9, 28))
        self.assertEqual(a["inicio"].strftime("%H:%M"), "15:30")
        self.assertEqual(a["fin"].strftime("%H:%M"), "16:30")

    def test_nocturno_y_cambio_de_mes(self):
        alertas = evaluar_cobertura(self.config("18:00", "02:00", "entrada"), date(2026, 10, 1))
        self.assertTrue(alertas)
        self.assertTrue(all(a["inicio"].hour == 18 and a["fin"].hour == 19 for a in alertas))
        self.assertTrue(all(a["inicio"].date() >= date(2026, 10, 1) for a in alertas))

    def test_deficit_con_personal_presente(self):
        config = self.config()
        for area in config["areas"].values():
            area["cobertura"]["N"] = 2
            area["dias_libres"]["A"] = "miércoles"
        alertas = evaluar_cobertura(config, date(2026, 9, 1))
        a = next(a for a in alertas if a["inicio"].date() == date(2026, 9, 28))
        self.assertEqual((a["presentes"], a["minimo"]), (1, 2))


if __name__ == "__main__":
    unittest.main()
