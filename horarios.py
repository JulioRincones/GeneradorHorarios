"""Generador de horarios rotativos y Excel, sin dependencias externas."""

import argparse
import calendar
import json
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from zipfile import ZIP_DEFLATED, ZipFile

BASE = Path(__file__).resolve().parent
AREAS = ("Cocina", "Barra", "Garzones")
DIAS = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
DIAS_COMPLETOS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MESES = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre")
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def entero(valor, nombre, minimo=0):
    if type(valor) is not int or valor < minimo:
        raise ValueError(f"{nombre} debe ser un entero mayor o igual a {minimo}.")
    return valor


def numero_dia(valor):
    if isinstance(valor, str):
        normalizado = unicodedata.normalize("NFKD", valor.strip().casefold())
        normalizado = "".join(c for c in normalizado if not unicodedata.combining(c))
        dias = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
        if normalizado in dias:
            return dias.index(normalizado)
    raise ValueError("El día libre debe ser lunes, martes, miércoles, jueves, viernes, sábado o domingo.")


def validar(config):
    if not isinstance(config, dict):
        raise ValueError("La configuración debe ser un objeto JSON.")
    if not isinstance(config.get("empresa"), str) or not config["empresa"].strip():
        raise ValueError("Indica el nombre de la empresa.")
    turnos = config.get("turnos")
    if not isinstance(turnos, dict) or not turnos:
        raise ValueError("Define al menos un turno.")
    for codigo, descripcion in turnos.items():
        if not codigo.strip() or codigo == "LIBRE" or len(codigo) > 12:
            raise ValueError("Usa códigos de turno de 1 a 12 caracteres, distintos de LIBRE.")
        if not isinstance(descripcion, str) or not descripcion.strip():
            raise ValueError(f"Falta la descripción del turno {codigo}.")
    areas = config.get("areas")
    if not isinstance(areas, dict) or set(areas) != set(AREAS):
        raise ValueError("Define exactamente las áreas Cocina, Barra y Garzones.")
    for nombre, area in areas.items():
        if not isinstance(area, dict):
            raise ValueError(f"Configuración inválida en {nombre}.")
        empleados = area.get("empleados")
        if not isinstance(empleados, list) or not empleados:
            raise ValueError(f"Agrega empleados en {nombre}.")
        if any(not isinstance(e, str) or not e.strip() for e in empleados):
            raise ValueError(f"Hay nombres vacíos o inválidos en {nombre}.")
        if len({e.strip().casefold() for e in empleados}) != len(empleados):
            raise ValueError(f"Hay nombres repetidos en {nombre}.")
        cobertura = area.get("cobertura")
        if not isinstance(cobertura, dict) or not cobertura:
            raise ValueError(f"Define la cobertura diaria en {nombre}.")
        for turno, cantidad in cobertura.items():
            if turno not in turnos:
                raise ValueError(f"Turno desconocido en {nombre}: {turno}.")
            entero(cantidad, f"Cobertura de {turno} en {nombre}")
        puestos = sum(cobertura.values())
        if puestos == 0 or puestos > len(empleados):
            raise ValueError(f"{nombre}: la cobertura debe ser entre 1 y {len(empleados)} personas por día.")
        entero(area.get("desfase", 0), f"Desfase de {nombre}")
        seleccion = area.get("turnos_semanales", {})
        if not isinstance(seleccion, dict):
            raise ValueError(f"{nombre}: turnos_semanales debe ser un objeto con fechas de lunes.")
        for lunes, asignaciones in seleccion.items():
            try:
                fecha = date.fromisoformat(lunes)
                if fecha.weekday() != 0 or fecha.isoformat() != lunes:
                    raise ValueError
            except (ValueError, TypeError):
                raise ValueError(f"{nombre}: {lunes} debe ser un lunes en formato AAAA-MM-DD.") from None
            if not isinstance(asignaciones, dict):
                raise ValueError(f"{nombre}, {lunes}: indica un turno por persona.")
            for persona, turno in asignaciones.items():
                if persona not in empleados:
                    raise ValueError(f"{nombre}: empleado desconocido en turnos_semanales: {persona}.")
                if not isinstance(turno, str) or turno not in turnos:
                    raise ValueError(f"{nombre}, {persona}: turno semanal desconocido: {turno}.")
        libres = area.get("dias_libres", {})
        if not isinstance(libres, dict):
            raise ValueError(f"{nombre}: dias_libres debe asociar nombres con días de la semana.")
        dias_libres = []
        for empleado, dia in libres.items():
            if empleado not in empleados:
                raise ValueError(f"{nombre}: empleado desconocido en dias_libres: {empleado}.")
            try:
                dias_libres.append(numero_dia(dia))
            except ValueError as error:
                raise ValueError(f"{nombre}, {empleado}: {error}") from None
        for dia in range(7):
            disponibles = len(empleados) - dias_libres.count(dia)
            if disponibles < puestos:
                raise ValueError(
                    f"{nombre}: el {DIAS_COMPLETOS[dia]} hay {disponibles} personas disponibles "
                    f"para {puestos} puestos. Cambia los días libres o la cobertura."
                )
    try:
        date.fromisoformat(config["inicio_rotacion"])
    except (KeyError, ValueError, TypeError):
        raise ValueError("inicio_rotacion debe ser una fecha AAAA-MM-DD.") from None


def generar(config, inicio, semanas, *, fin=None):
    validar(config)
    entero(semanas, "Semanas", 1)
    if semanas > 52:
        raise ValueError("Genera como máximo 52 semanas por archivo.")
    origen = date.fromisoformat(config["inicio_rotacion"])
    fechas = [inicio + timedelta(days=i) for i in range(semanas * 7)]
    if fin is not None:
        fechas = [dia for dia in fechas if dia <= fin]
    resultado = {}
    for nombre in AREAS:
        area = config["areas"][nombre]
        empleados = area["empleados"]
        puestos = [t for t in config["turnos"] for _ in range(area["cobertura"].get(t, 0))]
        # Cada persona recorre todos los puestos y luego los días libres.
        ciclo = puestos + ["LIBRE"] * (len(empleados) - len(puestos))
        resultado[nombre] = {
            empleado: [ciclo[(i + (dia - origen).days + area.get("desfase", 0)) % len(ciclo)]
                       for dia in fechas]
            for i, empleado in enumerate(empleados)
        }
        libres = {e: numero_dia(d) for e, d in area.get("dias_libres", {}).items()}
        for columna, dia in enumerate(fechas):
            ausentes = {e for e, d in libres.items() if d == dia.weekday()}
            lunes = (dia - timedelta(days=dia.weekday())).isoformat()
            seleccion = area.get("turnos_semanales", {}).get(lunes, {})
            if seleccion:
                pendientes = dict(area["cobertura"])
                for empleado in empleados:
                    turno = seleccion.get(empleado) if empleado not in ausentes else None
                    resultado[nombre][empleado][columna] = turno or "LIBRE"
                    if turno:
                        pendientes[turno] = pendientes.get(turno, 0) - 1
                        if pendientes[turno] < 0:
                            raise ValueError(
                                f"{nombre}, {dia:%d/%m/%Y}: las selecciones semanales del turno "
                                f"{turno} superan la cobertura. Ajusta la selección o la cobertura."
                            )
                disponibles = [e for e in empleados if e not in seleccion and e not in ausentes]
                offset = ((dia - origen).days + area.get("desfase", 0)) % max(1, len(disponibles))
                disponibles = disponibles[offset:] + disponibles[:offset]
                vacantes = [t for t in config["turnos"] for _ in range(pendientes.get(t, 0))]
                if len(vacantes) > len(disponibles):
                    raise ValueError(f"{nombre}, {dia:%d/%m/%Y}: no se puede cubrir la selección semanal.")
                for empleado, turno in zip(disponibles, vacantes):
                    resultado[nombre][empleado][columna] = turno
                continue
            vacantes = []
            for empleado in empleados:
                if empleado in ausentes:
                    turno = resultado[nombre][empleado][columna]
                    if turno != "LIBRE":
                        vacantes.append(turno)
                    resultado[nombre][empleado][columna] = "LIBRE"
            # La prioridad depende de la fecha, no del inicio de la exportación.
            offset = ((dia - origen).days + area.get("desfase", 0)) % len(empleados)
            orden = empleados[offset:] + empleados[:offset]
            reemplazos = [e for e in orden if e not in ausentes
                          and resultado[nombre][e][columna] == "LIBRE"]
            for turno, empleado in zip(vacantes, reemplazos):
                resultado[nombre][empleado][columna] = turno
    return fechas, resultado


def generar_mes(config, mes):
    inicio = mes.replace(day=1)
    cantidad = calendar.monthrange(inicio.year, inicio.month)[1]
    fechas, horarios = generar(config, inicio, (cantidad + 6) // 7,
                               fin=inicio.replace(day=cantidad))
    return fechas[:cantidad], {
        area: {persona: turnos[:cantidad] for persona, turnos in empleados.items()}
        for area, empleados in horarios.items()
    }


def leer_mes(valor):
    try:
        if len(valor) != 7:
            raise ValueError
        return date.fromisoformat(valor + "-01")
    except ValueError:
        raise argparse.ArgumentTypeError("Indica el mes como AAAA-MM, por ejemplo 2026-09.") from None


def xml(elemento):
    return tostring(elemento, encoding="utf-8", xml_declaration=True)


def hoja(config, nombre, fechas, horarios):
    root = Element("worksheet", xmlns=NS)
    vistas = SubElement(root, "sheetViews")
    SubElement(vistas, "sheetView", workbookViewId="0", showGridLines="0")
    SubElement(root, "sheetFormatPr", defaultRowHeight="24")
    columnas = SubElement(root, "cols")
    SubElement(columnas, "col", min="1", max="7", width="19", customWidth="1")
    datos = SubElement(root, "sheetData")
    fusiones, saltos = [], []
    fila = 0

    def agregar(valores, estilos=None, alto=24):
        nonlocal fila
        fila += 1
        row = SubElement(datos, "row", r=str(fila), ht=str(alto), customHeight="1")
        for i, valor in enumerate(valores):
            celda = SubElement(row, "c", r=f"{chr(65+i)}{fila}", t="inlineStr",
                               s=str(estilos[i] if estilos else 0))
            SubElement(SubElement(celda, "is"), "t").text = str(valor)

    indices = {dia: i for i, dia in enumerate(fechas)}
    meses = sorted({(dia.year, dia.month) for dia in fechas})
    calendario = calendar.Calendar(firstweekday=calendar.MONDAY)
    for anio, mes in meses:
        semanas = calendario.monthdayscalendar(anio, mes)
        for numero, (empleado, turnos) in enumerate(horarios.items()):
            # Dos calendarios completos por página, sin cortar trabajadores.
            if numero % 2 == 0:
                if fila:
                    saltos.append(fila)
                agregar([f"{MESES[mes-1]} {anio} · {nombre}"], [1], 32)
                fusiones.append(f"A{fila}:G{fila}")
                agregar([config["empresa"]], [0], 22)
                fusiones.append(f"A{fila}:G{fila}")
            agregar([empleado], [2], 26)
            fusiones.append(f"A{fila}:G{fila}")
            agregar([d.capitalize() for d in DIAS_COMPLETOS], [2]*7, 24)
            for semana in semanas:
                valores, formatos = [], []
                for dia in semana:
                    indice = indices.get(date(anio, mes, dia)) if dia else None
                    if indice is None:
                        valores.append("" if not dia else f"{dia}\nFuera del período")
                        formatos.append(0)
                    else:
                        turno = turnos[indice]
                        texto = "LIBRE" if turno == "LIBRE" else config["turnos"][turno]
                        valores.append(f"{dia}\n{texto}")
                        formatos.append(3 if turno == "LIBRE" else 4)
                agregar(valores, formatos, 60)
            agregar([], alto=14)
    merges = SubElement(root, "mergeCells", count=str(len(fusiones)))
    for ref in fusiones:
        SubElement(merges, "mergeCell", ref=ref)
    SubElement(root, "printOptions", horizontalCentered="1")
    SubElement(root, "pageMargins", left="0.25", right="0.25", top="0.35", bottom="0.35", header="0.15", footer="0.15")
    SubElement(root, "pageSetup", paperSize="9", orientation="portrait", scale="65")
    footer = SubElement(root, "headerFooter")
    SubElement(footer, "oddFooter").text = "&C&P / &N"
    if saltos:
        breaks = SubElement(root, "rowBreaks", count=str(len(saltos)), manualBreakCount=str(len(saltos)))
        for numero in saltos:
            SubElement(breaks, "brk", id=str(numero), min="0", max="16383", man="1")
    return xml(root), fila


def estilos():
    root = Element("styleSheet", xmlns=NS)
    fonts = SubElement(root, "fonts", count="2")
    for negrita in (False, True):
        font = SubElement(fonts, "font")
        SubElement(font, "sz", val="11")
        SubElement(font, "name", val="Calibri")
        if negrita:
            SubElement(font, "b")
    fills = SubElement(root, "fills", count="4")
    for patron, color in (("none", None), ("gray125", None), ("solid", "FFD9E2F3"), ("solid", "FFE7E6E6")):
        fill = SubElement(SubElement(fills, "fill"), "patternFill", patternType=patron)
        if color:
            SubElement(fill, "fgColor", rgb=color)
            SubElement(fill, "bgColor", indexed="64")
    borders = SubElement(root, "borders", count="1")
    border = SubElement(borders, "border")
    for lado in ("left", "right", "top", "bottom"):
        SubElement(SubElement(border, lado, style="hair"), "color", rgb="FFAAAAAA")
    SubElement(border, "diagonal")
    masters = SubElement(root, "cellStyleXfs", count="1")
    SubElement(masters, "xf", numFmtId="0", fontId="0", fillId="0", borderId="0")
    xfs = SubElement(root, "cellXfs", count="5")
    for font, fill, align in ((0, 0, "left"), (1, 2, "left"), (1, 2, "center"), (0, 3, "center"), (0, 0, "center")):
        xf = SubElement(xfs, "xf", numFmtId="0", fontId=str(font), fillId=str(fill), borderId="0", xfId="0", applyAlignment="1")
        SubElement(xf, "alignment", horizontal=align, vertical="center", wrapText="1")
    styles = SubElement(root, "cellStyles", count="1")
    SubElement(styles, "cellStyle", name="Normal", xfId="0", builtinId="0")
    return xml(root)


def exportar(config, fechas, horarios, destino):
    relns = "http://schemas.openxmlformats.org/package/2006/relationships"
    office = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    content = Element("Types", xmlns="http://schemas.openxmlformats.org/package/2006/content-types")
    SubElement(content, "Default", Extension="rels", ContentType="application/vnd.openxmlformats-package.relationships+xml")
    SubElement(content, "Default", Extension="xml", ContentType="application/xml")
    workbook = Element("workbook", xmlns=NS, attrib={"xmlns:r": office})
    sheets = SubElement(workbook, "sheets")
    nombres = SubElement(workbook, "definedNames")
    rels = Element("Relationships", xmlns=relns)
    archivos = {"xl/styles.xml": estilos()}
    for i, nombre in enumerate(AREAS, 1):
        ruta = f"worksheets/sheet{i}.xml"
        archivos[f"xl/{ruta}"], ultima = hoja(config, nombre, fechas, horarios[nombre])
        SubElement(sheets, "sheet", name=nombre, sheetId=str(i), attrib={"r:id": f"rId{i}"})
        SubElement(nombres, "definedName", name="_xlnm.Print_Area", localSheetId=str(i-1)).text = f"'{nombre}'!$A$1:$G${ultima}"
        SubElement(rels, "Relationship", Id=f"rId{i}", Type=f"{office}/worksheet", Target=ruta)
    SubElement(rels, "Relationship", Id="rId4", Type=f"{office}/styles", Target="styles.xml")
    archivos["xl/workbook.xml"] = xml(workbook)
    for ruta in archivos:
        tipo = "worksheet" if "/worksheets/" in ruta else "styles" if ruta.endswith("styles.xml") else "sheet.main"
        SubElement(content, "Override", PartName=f"/{ruta}", ContentType=f"application/vnd.openxmlformats-officedocument.spreadsheetml.{tipo}+xml")
    raizrels = Element("Relationships", xmlns=relns)
    SubElement(raizrels, "Relationship", Id="rId1", Type=f"{office}/officeDocument", Target="xl/workbook.xml")
    archivos.update({"[Content_Types].xml": xml(content), "_rels/.rels": xml(raizrels), "xl/_rels/workbook.xml.rels": xml(rels)})
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    # Evita sobrescribir un horario que el usuario ya haya ajustado en Excel.
    with ZipFile(destino, "x", ZIP_DEFLATED) as archivo:
        for ruta, contenido in archivos.items():
            archivo.writestr(ruta, contenido)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=BASE / "configuracion.json")
    periodo = parser.add_mutually_exclusive_group()
    periodo.add_argument("--mes", type=leer_mes, help="Mes completo AAAA-MM (por defecto: mes actual)")
    periodo.add_argument("--inicio", type=date.fromisoformat, help="Inicio de un período personalizado AAAA-MM-DD")
    parser.add_argument("--semanas", type=int, help="Duración del período personalizado; requiere --inicio")
    parser.add_argument("--salida", type=Path, help="Ruta del archivo .xlsx")
    args = parser.parse_args()
    if args.semanas is not None and args.inicio is None:
        parser.error("--semanas requiere --inicio; para un mes completo usa --mes AAAA-MM.")
    mes = args.mes or date.today().replace(day=1)
    semanas = args.semanas if args.semanas is not None else 4
    etiqueta = f"{args.inicio}_{semanas}semanas" if args.inicio else f"{mes:%Y-%m}"
    destino = args.salida or BASE / "salidas" / f"horarios_{etiqueta}.xlsx"
    try:
        if destino.suffix.lower() != ".xlsx":
            raise ValueError("El archivo de salida debe terminar en .xlsx.")
        config = json.loads(args.config.read_text(encoding="utf-8-sig"))
        fechas, horarios = generar(config, args.inicio, semanas) if args.inicio else generar_mes(config, mes)
        exportar(config, fechas, horarios, destino)
    except FileExistsError:
        parser.exit(1, f"El archivo ya existe: {destino}. Usa otro nombre con --salida.\n")
    except (OSError, ValueError) as error:
        parser.exit(1, f"No se pudo generar el horario: {error}\n")
    print(f"Excel generado: {destino.resolve()}")


if __name__ == "__main__":
    main()
