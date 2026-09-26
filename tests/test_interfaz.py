import json
import unittest
from datetime import date

from horarios import BASE, selecciones_del_area
from interfaz import guardar_persona, lunes_del_mes, guardar_turno
from horarios import horario_del_dia, ajustar_horas
from datetime import timedelta


class InterfazTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((BASE / "configuracion.json").read_text(encoding="utf-8"))
        self.config.pop("rotacion_mensual", None)
        self.config["areas"]["Cocina"] = {
            "empleados": ["Ana", "Luis", "Carla", "Pedro"],
            "dias_libres": {"Ana": "lunes", "Luis": "martes", "Carla": "miércoles", "Pedro": "jueves"},
            "cobertura": {"M": 1, "T": 1, "I": 0},
            "turnos_por_mes": {"2026-09": {"Ana": ["M", "T", "M", "T", "M"]}},
        }

    def test_crear_y_editar_turno_por_dia(self):
        dias = [["08:00", "16:00"] for _ in range(7)]
        dias[5] = ["20:00", "04:00"]
        nuevo = guardar_turno(self.config, "N", "Nuevo", dias, "entrada")
        self.assertNotIn("N", self.config["turnos"])
        self.assertIn("20:00 a 04:00 del día siguiente", horario_del_dia(nuevo, "N", date(2026, 10, 3)))
        self.assertTrue(all(a["cobertura"]["N"] == 0 for a in nuevo["areas"].values()))
        editado = guardar_turno(nuevo, "T", "Tarde nueva", dias, "salida", existente=True)
        fechas = [date(2026, 9, 28)+timedelta(days=i) for i in range(7)]
        calculados = ajustar_horas(editado, fechas, ["LIBRE"]+["T"]*6, "Ana")
        self.assertIn("08:00 a 15:00", calculados[1].descripcion)
        self.assertIn("20:00 a 04:00", calculados[5].descripcion)
        self.assertEqual(sum(t.minutos for t in calculados), 45*60)

    def test_turno_invalido_o_duplicado(self):
        for codigo, dias in (("M", [["09:00", "17:00"]]*7),
                             ("LIBRE", [["09:00", "17:00"]]*7),
                             ("N", [["25:00", "17:00"]]*7),
                             ("N", [["09:00", "09:00"]]*7)):
            with self.subTest(codigo=codigo, dias=dias):
                with self.assertRaises(ValueError):
                    guardar_turno(self.config, codigo, "Nombre", dias, "salida")

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

    def test_encargado_renombrado_y_desactivado(self):
        nuevo = guardar_persona(self.config, "Cocina", "Ana", "Andrea", "lunes", 0,
                                date(2026, 9, 1), ["M"] * 5,
                                encargado=True, adicionales={"2026-09-02", "2026-10-01"})
        self.assertEqual(nuevo["areas"]["Cocina"]["encargados"]["Andrea"],
                         ["2026-09-02", "2026-10-01"])
        nuevo = guardar_persona(nuevo, "Cocina", "Andrea", "Andrea", "lunes", 0,
                                date(2026, 9, 1), ["M"] * 5, encargado=False)
        self.assertNotIn("Andrea", nuevo["areas"]["Cocina"]["encargados"])

    def test_no_admite_dos_adicionales_en_semana_compartida(self):
        with self.assertRaisesRegex(ValueError, "un día libre adicional"):
            guardar_persona(self.config, "Cocina", "Ana", "Ana", "lunes", 0,
                            date(2026, 9, 1), ["M"] * 5, encargado=True,
                            adicionales={"2026-09-30", "2026-10-01"})


if __name__ == "__main__":
    unittest.main()
