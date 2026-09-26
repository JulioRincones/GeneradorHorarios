import json
import tempfile
import unittest
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from horarios import BASE, NS, exportar, generar, generar_mes, hoja, numero_dia, selecciones_del_area, ajustar_horas, horario_del_dia


class HorariosTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((BASE / "configuracion.json").read_text(encoding="utf-8"))
        for area in self.config["areas"].values():
            area.pop("turnos_por_mes", None)
        # Los casos unitarios no dependen de personas añadidas desde la interfaz.
        self.config["areas"]["Cocina"] = {
            "empleados": ["Ana", "Luis", "Carla", "Pedro"],
            "dias_libres": {"Ana": "lunes", "Luis": "martes", "Carla": "miércoles", "Pedro": "jueves"},
            "cobertura": {"M": 1, "T": 1, "I": 0}, "desfase": 0,
        }
        self.inicio = date(2026, 9, 28)

    def test_reduccion_horaria_por_tipo(self):
        fechas = [self.inicio + timedelta(days=i) for i in range(7)]
        for codigo, texto, total in (("M", "09:00 a 16:00", 45),
                                     ("T", "17:00 a 00:00", 45),
                                     ("I", "13:00 a 18:00", 33)):
            with self.subTest(codigo=codigo):
                turnos = ajustar_horas(self.config, fechas, ["LIBRE"] + [codigo]*6, "Ana")
                self.assertEqual(sum(t.minutos for t in turnos), total*60)
                self.assertEqual([t.reducido for t in turnos], [False, True, True, True, False, False, False])
                self.assertIn(texto, turnos[1].descripcion)
                self.assertEqual(turnos[4].descripcion, horario_del_dia(self.config, codigo, fechas[4]))
                self.assertEqual(turnos[0].horas_semana, total)

    def test_domingo_libre_sin_reducciones_y_maximo(self):
        fechas = [self.inicio + timedelta(days=i) for i in range(7)]
        turnos = ajustar_horas(self.config, fechas, ["LIBRE"] + ["M"]*5 + ["LIBRE"], "Ana")
        self.assertEqual(sum(t.minutos for t in turnos), 40*60)
        self.assertFalse(any(t.reducido for t in turnos))
        self.config["turnos"]["M"] = "Mañana · 09:00 a 19:00"
        with self.assertRaisesRegex(ValueError, "máximo es 45"):
            ajustar_horas(self.config, fechas, ["LIBRE"] + ["M"]*6, "Ana")

    def test_horarios_segun_dia_y_descuentos(self):
        fechas = [self.inicio + timedelta(days=i) for i in range(7)]
        manana = ajustar_horas(self.config, fechas, ["LIBRE"] + ["M"]*6, "Ana")
        tarde = ajustar_horas(self.config, fechas, ["LIBRE"] + ["T"]*6, "Luis")
        self.assertIn("10:30 a 18:30", manana[5].descripcion)
        self.assertIn("10:00 a 18:00", manana[6].descripcion)
        self.assertIn("19:00 a 02:00 del día siguiente", tarde[3].descripcion)
        self.assertEqual(tarde[3].minutos, 420)
        for i in (4, 5):
            self.assertIn("18:00 a 02:00 del día siguiente", tarde[i].descripcion)
            self.assertEqual(tarde[i].minutos, 480)
        self.assertIn("14:00 a 22:00", tarde[6].descripcion)
        self.assertEqual(sum(t.minutos for t in tarde), 45*60)
        self.assertEqual(sum(t.minutos for t in manana), 45*60)
        sin_domingo = ajustar_horas(self.config, fechas, ["LIBRE"] + ["T"]*5 + ["LIBRE"], "Luis")
        self.assertIn("18:00 a 02:00", sin_domingo[3].descripcion)
        self.assertEqual(sum(t.minutos for t in sin_domingo), 40*60)

    def test_horas_continuas_entre_meses(self):
        _, completo = generar(self.config, self.inicio, 1)
        _, septiembre = generar_mes(self.config, date(2026, 9, 1))
        _, octubre = generar_mes(self.config, date(2026, 10, 1))
        for area, personas in completo.items():
            for persona, turnos in personas.items():
                separados = septiembre[area][persona][-3:] + octubre[area][persona][:4]
                self.assertEqual([(t.descripcion, t.minutos, t.horas_semana) for t in turnos],
                                 [(t.descripcion, t.minutos, t.horas_semana) for t in separados])

    def test_ejemplo_mensual_turnos_fijos_y_descansos(self):
        config = json.loads((BASE / "configuracion.json").read_text(encoding="utf-8"))
        fechas, resultado = generar(config, date(2026, 8, 31), 5)
        for nombre, area in config["areas"].items():
            for persona, lista in area["turnos_por_mes"]["2026-09"].items():
                domingos = []
                for semana, turno in enumerate(lista):
                    seleccion = resultado[nombre][persona][semana*7:semana*7+7]
                    self.assertEqual(set(seleccion) - {"LIBRE"}, {turno})
                    self.assertEqual(seleccion[:6].count("LIBRE"), 1)
                    self.assertEqual(seleccion[numero_dia(area["dias_libres"][persona])], "LIBRE")
                    domingos.append(seleccion[6] == "LIBRE")
                self.assertTrue(all(a != b for a, b in zip(domingos, domingos[1:])))
            for i, dia in enumerate(fechas):
                cobertura = area.get("cobertura_domingo", area["cobertura"]) if dia.weekday() == 6 else area["cobertura"]
                cuentas = Counter(turnos[i] for turnos in resultado[nombre].values())
                for turno, minimo in cobertura.items():
                    self.assertGreaterEqual(cuentas[turno], minimo)

    def test_mes_semanas_parciales_y_continuidad(self):
        area = self.config["areas"]["Cocina"]
        area["turnos_por_mes"] = {"2026-09": {"Ana": ["M", "T", "M", "T", "M"]},
                                 "2026-10": {"Ana": ["M", "T", "M", "T", "M"]}}
        fechas, completo = generar(self.config, date(2026, 9, 28), 1)
        _, septiembre = generar_mes(self.config, date(2026, 9, 1))
        _, octubre = generar_mes(self.config, date(2026, 10, 1))
        for nombre, empleados in completo.items():
            for persona, turnos in empleados.items():
                self.assertEqual(septiembre[nombre][persona][-3:] + octubre[nombre][persona][:4], turnos)

    def test_semanas_mensuales_de_cuatro_cinco_y_seis_filas(self):
        area = self.config["areas"]["Cocina"]
        for mes, cantidad, primer_lunes in (("2027-02", 4, "2027-02-01"),
                                           ("2026-09", 5, "2026-08-31"),
                                           ("2026-03", 6, "2026-02-23")):
            with self.subTest(mes=mes):
                area["turnos_por_mes"] = {mes: {"Ana": ["I"] * cantidad}}
                seleccion = selecciones_del_area("Cocina", area, self.config["turnos"])
                self.assertEqual(len(seleccion), cantidad)
                self.assertEqual(seleccion[primer_lunes], {"Ana": "I"})

    def test_seleccion_mensual_invalida_y_conflictos(self):
        area = self.config["areas"]["Cocina"]
        casos = [[], {"2026-13": {}}, {"2026-9": {}},
                 {"2026-09": {"Ana": ["M"]}},
                 {"2026-09": {"Ana": ["X"] * 5}},
                 {"2026-09": {"Otra": ["M"] * 5}},
                 {"2026-09": {"Ana": ["M"] * 5}, "2026-10": {"Ana": ["T"] * 5}}]
        for valor in casos:
            with self.subTest(valor=valor):
                area["turnos_por_mes"] = valor
                with self.assertRaises(ValueError):
                    generar_mes(self.config, date(2026, 9, 1))
        area["turnos_por_mes"] = {"2026-09": {"Ana": ["M"] * 5}}
        area["turnos_semanales"] = {"2026-09-28": {"Ana": "T"}}
        with self.assertRaisesRegex(ValueError, "contradictorios"):
            generar_mes(self.config, date(2026, 9, 1))

    def test_no_cambia_turno_mensual_para_cubrir_faltantes(self):
        area = self.config["areas"]["Cocina"]
        area["turnos_por_mes"] = {"2026-09": {e: ["M"] * 5 for e in area["empleados"]}}
        with self.assertRaisesRegex(ValueError, "no se puede cubrir"):
            generar_mes(self.config, date(2026, 9, 1))

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

    def test_encargado_adicional_sin_cambiar_domingos(self):
        _, anterior = generar(self.config, self.inicio, 2)
        self.config["areas"]["Cocina"]["encargados"] = {"Ana": ["2026-09-30", "2026-10-09"]}
        fechas, resultado = generar(self.config, self.inicio, 2)
        turnos = resultado["Cocina"]["Ana"]
        self.assertEqual(turnos[:6].count("LIBRE"), 2)
        self.assertEqual(turnos[7:13].count("LIBRE"), 2)
        self.assertEqual(turnos[6], anterior["Cocina"]["Ana"][6])
        self.assertEqual(turnos[13], anterior["Cocina"]["Ana"][13])
        self.assertEqual(turnos[2], "LIBRE")
        self.assertEqual(turnos[11], "LIBRE")
        _, octubre = generar_mes(self.config, date(2026, 10, 1))
        self.assertEqual(octubre["Cocina"]["Ana"][:11], turnos[3:])
        contenido, _ = hoja(self.config, "Cocina", fechas, resultado["Cocina"])
        self.assertIn("30\nLIBRE", contenido.decode("utf-8"))

    def test_encargado_descansos_invalidos(self):
        for extras in (["2026-10-04"], ["2026-09-28"], ["2026-09-30", "2026-10-01"],
                       ["2026-09-30", "2026-09-30"], ["invalida"]):
            with self.subTest(extras=extras):
                self.config["areas"]["Cocina"]["encargados"] = {"Ana": extras}
                with self.assertRaises(ValueError):
                    generar(self.config, self.inicio, 2)

    def test_adicional_respeta_cobertura(self):
        area = self.config["areas"]["Cocina"]
        area["cobertura"]["M"] = 2
        area["cobertura_domingo"] = {"M": 1, "T": 1}
        area["encargados"] = {"Ana": ["2026-09-30"]}
        with self.assertRaisesRegex(ValueError, "no se puede cubrir"):
            generar(self.config, self.inicio, 1)

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
                    esperado = turno.descripcion
                    self.assertEqual(texto, f"{dia.day}\n{esperado}")
                for columna in range(desplazamiento):
                    self.assertEqual(celdas[f"{chr(65+columna)}5"], "")
                self.assertEqual(len(root.find(f"{{{NS}}}rowBreaks")), 1)


if __name__ == "__main__":
    unittest.main()
