import json
import tempfile
import unittest
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from horarios import BASE, NS, exportar, generar, generar_mes, hoja, numero_dia


class HorariosTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((BASE / "configuracion.json").read_text(encoding="utf-8"))
        self.inicio = date(2026, 9, 28)

    def test_descansos_exactos_y_domingos_alternos(self):
        fechas, resultado = generar(self.config, date(2026, 12, 21), 8)
        for nombre, empleados in resultado.items():
            area = self.config["areas"][nombre]
            for persona, turnos in empleados.items():
                domingos = []
                for inicio in range(0, 56, 7):
                    semana = turnos[inicio:inicio+7]
                    self.assertEqual(semana[:6].count("LIBRE"), 1)
                    self.assertEqual(semana[numero_dia(area["dias_libres"][persona])], "LIBRE")
                    domingos.append(semana[6] == "LIBRE")
                    self.assertEqual(semana.count("LIBRE"), 1 + domingos[-1])
                self.assertTrue(all(a != b for a, b in zip(domingos, domingos[1:])))

    def test_continuidad(self):
        _, completo = generar(self.config, self.inicio, 4)
        _, posterior = generar(self.config, self.inicio + timedelta(days=14), 2)
        for area, empleados in posterior.items():
            for persona, turnos in empleados.items():
                self.assertEqual(turnos, completo[area][persona][14:])

    def test_grupos_dominicales_y_configuracion_obligatoria(self):
        area = self.config["areas"]["Cocina"]
        area["domingo_grupo"] = {"Ana": 1, "Luis": 0, "Carla": 1, "Pedro": 0}
        _, resultado = generar(self.config, date(2026, 1, 5), 2)
        self.assertNotEqual(resultado["Cocina"]["Ana"][6], "LIBRE")
        self.assertEqual(resultado["Cocina"]["Ana"][13], "LIBRE")
        area["dias_libres"]["Ana"] = "domingo"
        with self.assertRaisesRegex(ValueError, "lunes a sábado"):
            generar(self.config, self.inicio, 1)
        area["dias_libres"].pop("Ana")
        with self.assertRaisesRegex(ValueError, "lunes a sábado"):
            generar(self.config, self.inicio, 1)

    def test_cobertura_dominical_imposible(self):
        self.config["areas"]["Cocina"]["cobertura_domingo"] = {"M": 2, "T": 1}
        with self.assertRaisesRegex(ValueError, "domingo"):
            generar(self.config, self.inicio, 1)

    def test_dotacion_insuficiente(self):
        self.config["areas"]["Cocina"]["cobertura"]["M"] = 5
        with self.assertRaisesRegex(ValueError, "Cocina"):
            generar(self.config, self.inicio, 1)

    def test_excel_y_proteccion_archivo(self):
        self.config["areas"]["Cocina"]["dias_libres"]['=Ana & "Luis" <3'] = self.config["areas"]["Cocina"]["dias_libres"].pop("Ana")
        self.config["areas"]["Cocina"]["empleados"][0] = '=Ana & "Luis" <3'
        fechas, horarios = generar(self.config, self.inicio, 4)
        with tempfile.TemporaryDirectory() as carpeta:
            destino = Path(carpeta) / "horarios.xlsx"
            exportar(self.config, fechas, horarios, destino)
            with ZipFile(destino) as archivo:
                self.assertIsNone(archivo.testzip())
                for ruta in archivo.namelist():
                    ET.fromstring(archivo.read(ruta))
                libro = ET.fromstring(archivo.read("xl/workbook.xml"))
                self.assertEqual(len(libro.find(f"{{{NS}}}sheets")), 3)
                hoja = ET.fromstring(archivo.read("xl/worksheets/sheet1.xml"))
                self.assertEqual(len(hoja.find(f"{{{NS}}}rowBreaks")), 3)
                self.assertEqual(len(hoja.findall(f".//{{{NS}}}f")), 0)
            with self.assertRaises(FileExistsError):
                exportar(self.config, fechas, horarios, destino)

    def test_libres_fijos_y_cobertura(self):
        fechas, resultado = generar(self.config, date(2026, 9, 30), 8)
        for nombre, empleados in resultado.items():
            area = self.config["areas"][nombre]
            for columna, dia in enumerate(fechas):
                cuentas = Counter(turnos[columna] for turnos in empleados.values())
                for turno, cantidad in (area.get("cobertura_domingo", area["cobertura"]) if dia.weekday() == 6 else area["cobertura"]).items():
                    self.assertGreaterEqual(cuentas[turno], cantidad)
                for empleado, libre in area["dias_libres"].items():
                    if dia.weekday() == numero_dia(libre):
                        self.assertEqual(empleados[empleado][columna], "LIBRE")

    def test_libres_imposibles(self):
        self.config["areas"]["Cocina"]["dias_libres"] = {
            "Ana": "lunes", "Luis": "lunes", "Carla": "lunes", "Pedro": "jueves"
        }
        with self.assertRaisesRegex(ValueError, "Cocina: el lunes hay 1.*2 puestos"):
            generar(self.config, self.inicio, 1)

    def test_libres_invalidos(self):
        for libres in ({"Otra persona": "lunes"}, {"Ana": "luness"}, {"Ana": 1}, []):
            with self.subTest(libres=libres):
                self.config["areas"]["Cocina"]["dias_libres"] = libres
                with self.assertRaises(ValueError):
                    generar(self.config, self.inicio, 1)

    def test_dias_con_mayusculas_y_sin_tildes(self):
        self.assertEqual(numero_dia(" MIÉRCOLES "), 2)
        self.assertEqual(numero_dia("sabado"), 5)

    def test_meses_completos(self):
        for anio, mes, cantidad in ((2026, 9, 30), (2026, 2, 28), (2028, 2, 29), (2026, 12, 31)):
            with self.subTest(anio=anio, mes=mes):
                fechas, horarios = generar_mes(self.config, date(anio, mes, 15))
                self.assertEqual(fechas[0], date(anio, mes, 1))
                self.assertEqual(fechas[-1], date(anio, mes, cantidad))
                for area in horarios.values():
                    self.assertTrue(all(len(turnos) == cantidad for turnos in area.values()))

    def test_seleccion_semanal_tres_turnos_y_continuidad(self):
        area = self.config["areas"]["Cocina"]
        area["cobertura"]["I"] = 1
        area["cobertura_domingo"] = {"M": 0, "T": 0, "I": 0}
        area["turnos_semanales"] = {
            "2026-09-28": {"Ana": "M", "Luis": "T", "Carla": "I"},
            "2026-10-05": {"Ana": "I", "Luis": "M", "Carla": "T"},
        }
        fechas, horarios = generar(self.config, self.inicio, 2)
        for indice, dia in enumerate(fechas):
            lunes = (dia - timedelta(days=dia.weekday())).isoformat()
            for persona, turno in area["turnos_semanales"][lunes].items():
                origen = date.fromisoformat(self.config["inicio_rotacion"])
                libre_domingo = dia.weekday() == 6 and ((dia - origen).days // 7) % 2 == area["empleados"].index(persona) % 2
                esperado = "LIBRE" if libre_domingo or dia.weekday() == numero_dia(area["dias_libres"][persona]) else turno
                self.assertEqual(horarios["Cocina"][persona][indice], esperado)
            cuentas = Counter(t[indice] for t in horarios["Cocina"].values())
            for turno, cantidad in (area["cobertura_domingo"] if dia.weekday() == 6 else area["cobertura"]).items():
                self.assertGreaterEqual(cuentas[turno], cantidad)
        _, octubre = generar_mes(self.config, date(2026, 10, 1))
        for persona in area["empleados"]:
            self.assertEqual(octubre["Cocina"][persona][:11], horarios["Cocina"][persona][3:])

    def test_seleccion_semanal_invalida(self):
        for seleccion in ({"2026-09-29": {"Ana": "M"}},
                          {"2026-09-28": {"Ana": "X"}},
                          {"2026-09-28": {"Desconocido": "M"}},

                          {"2026-09-28": {e: "M" for e in self.config["areas"]["Cocina"]["empleados"]}}):
            with self.subTest(seleccion=seleccion):
                self.config["areas"]["Cocina"]["turnos_semanales"] = seleccion
                with self.assertRaises(ValueError):
                    generar(self.config, self.inicio, 1)

    def test_mes_no_valida_cobertura_del_mes_siguiente(self):
        self.config["areas"]["Cocina"]["turnos_semanales"] = {"2026-06-01": {"Ana": "I"}}
        fechas, _ = generar_mes(self.config, date(2026, 5, 1))
        self.assertEqual(fechas[-1], date(2026, 5, 31))

    def test_calendario_por_persona_lunes_a_domingo(self):
        for anio, mes in ((2026, 9), (2026, 3), (2028, 2)):
            with self.subTest(anio=anio, mes=mes):
                fechas, horarios = generar_mes(self.config, date(anio, mes, 1))
                contenido, _ = hoja(self.config, "Cocina", fechas, horarios["Cocina"])
                root = ET.fromstring(contenido)
                celdas = {c.attrib["r"]: c.findtext(f"{{{NS}}}is/{{{NS}}}t", "")
                          for c in root.findall(f".//{{{NS}}}c")}
                self.assertEqual(celdas["A3"], "Ana")
                self.assertEqual(celdas["A4"], "Lunes")
                self.assertEqual(celdas["G4"], "Domingo")
                desplazamiento = fechas[0].weekday()
                for indice, dia in enumerate(fechas):
                    fila = 5 + (desplazamiento + indice) // 7
                    columna = chr(65 + dia.weekday())
                    texto = celdas[f"{columna}{fila}"]
                    turno = horarios["Cocina"]["Ana"][indice]
                    esperado = "LIBRE" if turno == "LIBRE" else self.config["turnos"][turno]
                    self.assertEqual(texto, f"{dia.day}\n{esperado}")
                for columna in range(desplazamiento):
                    self.assertEqual(celdas[f"{chr(65+columna)}5"], "")
                self.assertEqual(len(root.find(f"{{{NS}}}rowBreaks")), 1)


if __name__ == "__main__":
    unittest.main()
