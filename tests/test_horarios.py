import json
import tempfile
import unittest
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from horarios import BASE, NS, exportar, generar, numero_dia


class HorariosTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((BASE / "configuracion.json").read_text(encoding="utf-8"))
        self.inicio = date(2026, 9, 28)

    def test_cobertura_y_equidad(self):
        for area in self.config["areas"].values():
            area.pop("dias_libres", None)
        _, resultado = generar(self.config, self.inicio, 12)
        for nombre, empleados in resultado.items():
            for dia in range(84):
                cuentas = Counter(turnos[dia] for turnos in empleados.values())
                for turno, cantidad in self.config["areas"][nombre]["cobertura"].items():
                    self.assertEqual(cuentas[turno], cantidad)
            balances = [Counter(turnos) for turnos in empleados.values()]
            self.assertTrue(all(balance == balances[0] for balance in balances))

    def test_continuidad(self):
        _, completo = generar(self.config, self.inicio, 4)
        _, posterior = generar(self.config, self.inicio + timedelta(days=14), 2)
        for area, empleados in posterior.items():
            for persona, turnos in empleados.items():
                self.assertEqual(turnos, completo[area][persona][14:])

    def test_dotacion_insuficiente(self):
        self.config["areas"]["Cocina"]["cobertura"]["M"] = 5
        with self.assertRaisesRegex(ValueError, "Cocina"):
            generar(self.config, self.inicio, 1)

    def test_excel_y_proteccion_archivo(self):
        self.config["areas"]["Cocina"]["dias_libres"].pop("Ana")
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
                for turno, cantidad in area["cobertura"].items():
                    self.assertEqual(cuentas[turno], cantidad)
                for empleado, libre in area["dias_libres"].items():
                    if dia.weekday() == numero_dia(libre):
                        self.assertEqual(empleados[empleado][columna], "LIBRE")

    def test_libres_imposibles(self):
        self.config["areas"]["Cocina"]["dias_libres"] = {
            "Ana": "lunes", "Luis": "lunes", "Carla": "lunes"
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


if __name__ == "__main__":
    unittest.main()
