"""Generador de horarios rotativos y Excel, sin dependencias externas."""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from zipfile import ZIP_DEFLATED, ZipFile

BASE = Path(__file__).resolve().parent
AREAS = ("Cocina", "Barra", "Garzones")
DIAS = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def entero(valor, nombre, minimo=0):
    if type(valor) is not int or valor < minimo:
        raise ValueError(f"{nombre} debe ser un entero mayor o igual a {minimo}.")
    return valor


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
    try:
        date.fromisoformat(config["inicio_rotacion"])
    except (KeyError, ValueError, TypeError):
        raise ValueError("inicio_rotacion debe ser una fecha AAAA-MM-DD.") from None


def generar(config, inicio, semanas):
    validar(config)
    entero(semanas, "Semanas", 1)
    if semanas > 52:
        raise ValueError("Genera como máximo 52 semanas por archivo.")
    origen = date.fromisoformat(config["inicio_rotacion"])
    fechas = [inicio + timedelta(days=i) for i in range(semanas * 7)]
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
    return fechas, resultado


def xml(elemento):
    return tostring(elemento, encoding="utf-8", xml_declaration=True)


def hoja(config, nombre, fechas, horarios):
    root = Element("worksheet", xmlns=NS)
    vistas = SubElement(root, "sheetViews")
    SubElement(vistas, "sheetView", workbookViewId="0", showGridLines="0")
    SubElement(root, "sheetFormatPr", defaultRowHeight="24")
    columnas = SubElement(root, "cols")
    SubElement(columnas, "col", min="1", max="1", width="28", customWidth="1")
    SubElement(columnas, "col", min="2", max="8", width="15", customWidth="1")
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

    for offset in range(0, len(fechas), 7):
        semana = fechas[offset:offset+7]
        agregar([f"{config['empresa']} · {nombre}"], [1], 30)
        fusiones.append(f"A{fila}:H{fila}")
        agregar([f"Del {semana[0]:%d/%m/%Y} al {semana[-1]:%d/%m/%Y}"], [0])
        fusiones.append(f"A{fila}:H{fila}")
        agregar(["Persona"] + [f"{DIAS[d.weekday()]} {d:%d/%m}" for d in semana], [2]*8, 28)
        for empleado, turnos in horarios.items():
            seleccion = turnos[offset:offset+7]
            agregar([empleado] + seleccion, [0] + [3 if t == "LIBRE" else 4 for t in seleccion])
        for codigo, descripcion in config["turnos"].items():
            agregar([f"{codigo}: {descripcion}"], alto=28)
            fusiones.append(f"A{fila}:H{fila}")
        agregar(["LIBRE: día sin turno asignado"])
        fusiones.append(f"A{fila}:H{fila}")
        if offset + 7 < len(fechas):
            saltos.append(fila)
    merges = SubElement(root, "mergeCells", count=str(len(fusiones)))
    for ref in fusiones:
        SubElement(merges, "mergeCell", ref=ref)
    SubElement(root, "printOptions", horizontalCentered="1")
    SubElement(root, "pageMargins", left="0.25", right="0.25", top="0.35", bottom="0.35", header="0.15", footer="0.15")
    SubElement(root, "pageSetup", paperSize="9", orientation="landscape", scale="85")
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
        SubElement(nombres, "definedName", name="_xlnm.Print_Area", localSheetId=str(i-1)).text = f"'{nombre}'!$A$1:$H${ultima}"
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
    parser.add_argument("--inicio", type=date.fromisoformat, default=date.today(), help="Primer día, AAAA-MM-DD (por defecto: hoy)")
    parser.add_argument("--semanas", type=int, default=4)
    parser.add_argument("--salida", type=Path, help="Ruta del archivo .xlsx")
    args = parser.parse_args()
    destino = args.salida or BASE / "salidas" / f"horarios_{args.inicio}_{args.semanas}semanas.xlsx"
    try:
        if destino.suffix.lower() != ".xlsx":
            raise ValueError("El archivo de salida debe terminar en .xlsx.")
        config = json.loads(args.config.read_text(encoding="utf-8-sig"))
        fechas, horarios = generar(config, args.inicio, args.semanas)
        exportar(config, fechas, horarios, destino)
    except FileExistsError:
        parser.exit(1, f"El archivo ya existe: {destino}. Usa otro nombre con --salida.\n")
    except (OSError, ValueError) as error:
        parser.exit(1, f"No se pudo generar el horario: {error}\n")
    print(f"Excel generado: {destino.resolve()}")


if __name__ == "__main__":
    main()
