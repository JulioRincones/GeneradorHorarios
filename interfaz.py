"""Interfaz de escritorio para Windows, basada en tkinter."""

import calendar
import copy
import json
import os
import re
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from horarios import (AREAS, BASE, DIAS_COMPLETOS, MESES, exportar, generar_mes,
                      selecciones_del_area, validar, descansos_encargados, numero_dia, descripcion_turno,
                      horario_del_dia, validar_detalle_turno, evaluar_cobertura, validar_jornadas, turno_rotacion_mensual, seleccion_para_fecha)


def lunes_del_mes(mes):
    primero = mes.replace(day=1)
    lunes = primero - timedelta(days=primero.weekday())
    cantidad = len(calendar.Calendar(0).monthdayscalendar(mes.year, mes.month))
    return [lunes + timedelta(weeks=i) for i in range(cantidad)]


def guardar_turno(config, codigo, nombre, dias, reduccion, existente=False):
    codigo = codigo.strip()
    if not codigo or len(codigo) > 12 or codigo == "LIBRE":
        raise ValueError("Usa un código de 1 a 12 caracteres, distinto de LIBRE.")
    if not existente and any(c.casefold() == codigo.casefold() for c in config["turnos"]):
        raise ValueError("Ese código ya existe. Selecciona el turno para editarlo.")
    detalle = {"nombre": nombre.strip(), "dias": dias, "reduccion": reduccion}
    validar_detalle_turno(detalle)
    nuevo = copy.deepcopy(config)
    nuevo.setdefault("turnos_detalle", {})[codigo] = detalle
    nuevo["turnos"][codigo] = f"{nombre.strip()} · {dias[0][0]} a {dias[0][1]}"
    for area in nuevo["areas"].values():
        area["cobertura"].setdefault(codigo, 0)
        if "cobertura_domingo" in area:
            area["cobertura_domingo"].setdefault(codigo, 0)
    return nuevo


def guardar_persona(config, area_nombre, anterior, nombre, libre, grupo, mes, turnos,
                    encargado=None, adicionales=None, jornada=None, domingo_turno=None):
    """Devuelve una copia editada sin perder otros meses ni grupos dominicales."""
    nuevo = copy.deepcopy(config)
    area = nuevo["areas"][area_nombre]
    nombre = nombre.strip()
    if not nombre:
        raise ValueError("Escribe el nombre de la persona.")
    if any(e.casefold() == nombre.casefold() and e != anterior for e in area["empleados"]):
        raise ValueError("Ya existe una persona con ese nombre en el área.")
    grupos = area.setdefault("domingo_grupo", {})
    for i, persona in enumerate(area["empleados"]):
        grupos.setdefault(persona, i % 2)
    if anterior:
        area["empleados"][area["empleados"].index(anterior)] = nombre
        mapas = [area["dias_libres"], grupos, area.setdefault("encargados", {}), area.setdefault("jornadas", {}), area.setdefault("domingo_turno", {})]
        mapas += list(area.get("turnos_semanales", {}).values())
        mapas += list(area.get("turnos_por_mes", {}).values())
        for mapa in mapas:
            if anterior in mapa:
                mapa[nombre] = mapa.pop(anterior)
    else:
        area["empleados"].append(nombre)
    area["dias_libres"][nombre] = libre
    grupos[nombre] = grupo
    if domingo_turno is not None:
        if domingo_turno == "":
            area.setdefault("domingo_turno", {}).pop(nombre, None)
        elif domingo_turno in ("M", "T") and domingo_turno in nuevo["turnos"]:
            area.setdefault("domingo_turno", {})[nombre] = domingo_turno
        else:
            raise ValueError("El turno del domingo debe ser mañana o tarde.")
    if jornada is not None:
        area.setdefault("jornadas", {})[nombre] = copy.deepcopy(jornada)
    if area.get("jornadas", {}).get(nombre, {}).get("tipo", "full_time") != "full_time":
        encargado = False
        area["dias_libres"].pop(nombre, None)
    if encargado is True:
        area.setdefault("encargados", {})[nombre] = sorted(adicionales or [])
    elif encargado is False:
        area.setdefault("encargados", {}).pop(nombre, None)
    validar_jornadas(area)
    descansos_encargados(area)
    for lunes, turno in zip(lunes_del_mes(mes), turnos):
        # Una semana compartida entre meses siempre representa una sola elección.
        for clave, personas in area.get("turnos_por_mes", {}).items():
            semanas = lunes_del_mes(date.fromisoformat(clave + "-01"))
            if nombre in personas and lunes in semanas:
                if turno is None:
                    # Convertir la lista a fechas permite dejar una semana automática.
                    lista = personas.pop(nombre)
                    for fecha, valor in zip(semanas, lista):
                        area.setdefault("turnos_semanales", {}).setdefault(fecha.isoformat(), {})[nombre] = valor
                else:
                    personas[nombre][semanas.index(lunes)] = turno
        asignaciones = area.setdefault("turnos_semanales", {}).setdefault(lunes.isoformat(), {})
        if turno is None:
            asignaciones.pop(nombre, None)
        else:
            asignaciones[nombre] = turno
    if (nuevo.get("rotacion_mensual", False) and all(t is not None for t in turnos)
            and area.get("jornadas", {}).get(nombre, {}).get("tipo", "full_time") == "full_time"):
        area.setdefault("turnos_por_mes", {}).setdefault(f"{mes:%Y-%m}", {})[nombre] = list(turnos)
    return nuevo


class Aplicacion(ttk.Frame):
    def __init__(self, root, ruta=BASE / "configuracion.json"):
        super().__init__(root, padding=18)
        self.root, self.ruta = root, Path(ruta)
        self.config = json.loads(self.ruta.read_text(encoding="utf-8-sig"))
        validar(self.config)
        self.modificado = False
        self.actualizacion_alertas = None
        self.ultimo_excel = None
        self.mes = date.today().replace(day=1)
        root.title("Horarios · Planificador de turnos")
        root.geometry("1180x720")
        root.minsize(900, 580)
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Treeview", rowheight=34, font=("Segoe UI", 10))
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TButton", padding=(10, 6))
        self.pack(fill="both", expand=True)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)
        ttk.Label(self, text="Planificador de horarios", font=("Segoe UI", 22, "bold")).grid(sticky="w")
        ttk.Label(self, text="1. Elige el mes    2. Edita las personas y sus turnos    3. Revisa y exporta").grid(sticky="w", pady=(4, 16))
        barra = ttk.Frame(self)
        barra.grid(row=2, sticky="ew", pady=(0, 14))
        ttk.Label(barra, text="Empresa").pack(side="left")
        self.empresa = tk.StringVar(value=self.config["empresa"])
        ttk.Entry(barra, textvariable=self.empresa, width=27).pack(side="left", padx=(8, 20))
        self.empresa.trace_add("write", self.cambiar_empresa)
        self.mes_var = tk.StringVar(value=MESES[self.mes.month-1])
        ttk.Combobox(barra, textvariable=self.mes_var, values=MESES, state="readonly", width=13).pack(side="left")
        self.anio = tk.StringVar(value=str(self.mes.year))
        ttk.Spinbox(barra, from_=2000, to=2100, textvariable=self.anio, width=6).pack(side="left", padx=8)
        ttk.Button(barra, text="Mostrar mes", command=self.cambiar_mes).pack(side="left")
        ttk.Button(barra, text="Administrar turnos", command=self.editar_turnos).pack(side="left", padx=8)
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=3, sticky="nsew")
        alarmas = ttk.LabelFrame(self, text="Alertas de cobertura", padding=10, width=270)
        alarmas.grid(row=3, column=1, sticky="nsew", padx=(12, 0))
        alarmas.grid_propagate(False)
        alarmas.columnconfigure(0, weight=1)
        alarmas.rowconfigure(2, weight=1)
        self.resumen_alertas = tk.StringVar(value="Evaluando…")
        ttk.Label(alarmas, textvariable=self.resumen_alertas, wraplength=230).grid(sticky="w", pady=(0, 8))
        ttk.Label(alarmas, text="Horas efectivas, incluidas reducciones y cierres nocturnos.", wraplength=230).grid(row=1, sticky="w", pady=(0, 8))
        self.texto_alertas = tk.Text(alarmas, width=28, wrap="word", font=("Segoe UI", 10),
                                    relief="flat", padx=6, pady=6, state="disabled")
        self.texto_alertas.grid(row=2, column=0, sticky="nsew")
        scroll_alertas = ttk.Scrollbar(alarmas, command=self.texto_alertas.yview)
        scroll_alertas.grid(row=2, column=1, sticky="ns")
        self.texto_alertas.configure(yscrollcommand=scroll_alertas.set)
        self.texto_alertas.tag_configure("critica", foreground="#b42318")
        self.texto_alertas.tag_configure("aviso", foreground="#855700")
        self.tablas = {}
        for nombre in AREAS:
            panel = ttk.Frame(self.notebook, padding=12)
            self.notebook.add(panel, text=nombre)
            panel.columnconfigure(0, weight=1)
            panel.rowconfigure(1, weight=1)
            acciones = ttk.Frame(panel)
            acciones.grid(sticky="ew", pady=(0, 10))
            for titulo, funcion in (("Agregar persona", lambda a=nombre: self.editar(a, True)),
                                     ("Editar selección", lambda a=nombre: self.editar(a)),
                                     ("Eliminar", lambda a=nombre: self.eliminar(a)),
                                     ("Cobertura mínima", lambda a=nombre: self.cobertura(a))):
                ttk.Button(acciones, text=titulo, command=funcion).pack(side="left", padx=(0, 8))
            tabla = ttk.Treeview(panel, show="headings", selectmode="browse")
            tabla.grid(row=1, column=0, sticky="nsew")
            scroll = ttk.Scrollbar(panel, orient="vertical", command=tabla.yview)
            scroll.grid(row=1, column=1, sticky="ns")
            horizontal = ttk.Scrollbar(panel, orient="horizontal", command=tabla.xview)
            horizontal.grid(row=2, column=0, sticky="ew")
            tabla.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
            tabla.bind("<Double-1>", lambda event, a=nombre: self.editar(a))
            self.tablas[nombre] = tabla
        ttk.Label(self, text="Cada turno elegido es fijo durante la semana. Se respetan el día libre y los domingos alternados.").grid(row=4, sticky="w", pady=(12, 6))
        pie = ttk.Frame(self)
        pie.grid(row=5, sticky="ew")
        for titulo, funcion in (("Guardar cambios", self.guardar), ("Vista previa", self.previa),
                                 ("Generar Excel…", self.generar), ("Abrir último Excel", self.abrir_excel)):
            ttk.Button(pie, text=titulo, command=funcion).pack(side="left", padx=(0, 8))
        self.estado = tk.StringVar(value="Listo. Selecciona una persona y pulsa Editar selección.")
        ttk.Label(self, textvariable=self.estado).grid(row=6, sticky="w", pady=(12, 0))
        root.protocol("WM_DELETE_WINDOW", self.cerrar)
        root.bind("<Control-s>", lambda event: self.guardar())
        self.refrescar()

    def cambiar_empresa(self, *_):
        self.config["empresa"] = self.empresa.get()
        self.marcar()

    def marcar(self):
        self.modificado = True
        self.estado.set("Hay cambios sin guardar.")
        self.programar_alertas()

    def programar_alertas(self):
        if self.actualizacion_alertas is not None:
            self.root.after_cancel(self.actualizacion_alertas)
        self.actualizacion_alertas = self.root.after(200, self.actualizar_alertas)

    def actualizar_alertas(self):
        self.actualizacion_alertas = None
        self.texto_alertas.configure(state="normal")
        self.texto_alertas.delete("1.0", "end")
        try:
            alertas = evaluar_cobertura(self.config, self.mes)
            vacios = sum(a["presentes"] == 0 for a in alertas)
            self.resumen_alertas.set(f"{len(alertas)} tramos con déficit · {vacios} sin personal")
            if not alertas:
                self.texto_alertas.insert("end", "Cobertura completa para los mínimos configurados.\n")
            for a in alertas:
                texto = (f"{a['area']} · {a['inicio']:%d/%m}\n"
                         f"{a['inicio']:%H:%M} – {a['fin']:%H:%M}"
                         + (" (+1 día)" if a['fin'].date() != a['inicio'].date() else "")
                         + f"\n{a['presentes']} presentes / {a['minimo']} necesarios\n"
                         + ("SIN PERSONAL\n" if a['presentes'] == 0 else "") + "\n")
                self.texto_alertas.insert("end", texto, "critica" if a["presentes"] == 0 else "aviso")
        except (ValueError, OverflowError) as error:
            self.resumen_alertas.set("No se pudo evaluar la cobertura")
            self.texto_alertas.insert("end", str(error), "critica")
        finally:
            self.texto_alertas.configure(state="disabled")

    def cambiar_mes(self):
        try:
            self.mes = date(int(self.anio.get()), MESES.index(self.mes_var.get())+1, 1)
            self.refrescar()
        except ValueError:
            messagebox.showerror("Mes inválido", "Indica un año válido.", parent=self.root)

    def refrescar(self):
        semanas = lunes_del_mes(self.mes)
        self.root.title(f"Horarios · {MESES[self.mes.month-1]} {self.mes.year}")
        for nombre, tabla in self.tablas.items():
            area = self.config["areas"][nombre]
            seleccion = selecciones_del_area(nombre, area, self.config["turnos"])
            columnas = ["persona", "libre", "domingo"] + [str(i) for i in range(len(semanas))]
            tabla.configure(columns=columnas)
            for columna, titulo in zip(columnas, ["Persona", "Día libre", "Domingos"] + [f"S{i+1} · {d:%d/%m}" for i, d in enumerate(semanas)]):
                tabla.heading(columna, text=titulo)
                tabla.column(columna, width=150 if columna == "persona" else 115, minwidth=100)
            tabla.delete(*tabla.get_children())
            for i, persona in enumerate(area["empleados"]):
                etiqueta = persona + (" · Encargado" if persona in area.get("encargados", {}) else "")
                jornada = area.get("jornadas", {}).get(persona, {"tipo": "full_time"})
                tipo = jornada["tipo"]
                etiqueta += {"full_time": "", "part_time_30": " · PT30", "part_time_20": " · PT20"}[tipo]
                libre = area["dias_libres"].get(persona, "").capitalize() if tipo == "full_time" else "Según días elegidos"
                domingos = f"Grupo {area.get('domingo_grupo', {}).get(persona, i % 2)+1}" if tipo == "full_time" else ("Trabaja" if 6 in jornada["dias"] else "Libre")
                if tipo != "part_time_20" and persona in area.get("domingo_turno", {}):
                    domingos += f" · {area['domingo_turno'][persona]}"
                valores = [etiqueta, libre, domingos]
                valores += ["10 h 30 min" if tipo == "part_time_20" else (
                    seleccion_para_fecha(self.config, area, seleccion, persona, max(d, self.mes)) or "Sin selección") for d in semanas]
                tabla.insert("", "end", iid=str(i), values=valores)
        self.programar_alertas()

    def dialogo(self, titulo):
        ventana = tk.Toplevel(self.root)
        ventana.title(titulo)
        ventana.transient(self.root)
        ventana.resizable(False, False)
        ventana.grab_set()
        marco = ttk.Frame(ventana, padding=20)
        marco.pack(fill="both", expand=True)
        return ventana, marco

    def editar(self, nombre, agregar=False):
        tabla = self.tablas[nombre]
        if not agregar and not tabla.selection():
            messagebox.showinfo("Selecciona una persona", "Selecciona una fila para editarla.", parent=self.root)
            return
        area = self.config["areas"][nombre]
        indice = len(area["empleados"]) if agregar else int(tabla.selection()[0])
        anterior = None if agregar else area["empleados"][indice]
        ventana, marco = self.dialogo(f"{'Agregar' if agregar else 'Editar'} persona · {nombre}")
        persona = tk.StringVar(value=anterior or "")
        libre = tk.StringVar(value=area["dias_libres"].get(anterior, "lunes"))
        grupo = tk.StringVar(value=f"Grupo {area.get('domingo_grupo', {}).get(anterior, indice % 2)+1}")
        ttk.Label(marco, text="Nombre").grid(row=0, column=0, sticky="w", pady=5)
        entrada = ttk.Entry(marco, textvariable=persona, width=38)
        entrada.grid(row=0, column=1, sticky="ew")
        entrada.focus_set()
        controles_full = []
        for fila, titulo, variable, opciones in ((1, "Día libre fijo", libre, DIAS_COMPLETOS[:6]),
                                                  (2, "Domingos alternados", grupo, ("Grupo 1", "Grupo 2"))):
            ttk.Label(marco, text=titulo).grid(row=fila, column=0, sticky="w", padx=(0, 15), pady=6)
            control = ttk.Combobox(marco, textvariable=variable, values=opciones, state="readonly", width=36)
            control.grid(row=fila, column=1)
            controles_full.append(control)
        origen = date.fromisoformat(self.config["inicio_rotacion"])
        domingo = origen + timedelta(days=6-origen.weekday())
        ttk.Label(marco, text=f"Grupo 1: libre el {domingo:%d/%m/%Y} y cada 14 días.\nGrupo 2: libre el {domingo+timedelta(days=7):%d/%m/%Y} y cada 14 días.").grid(row=3, columnspan=2, sticky="w", pady=10)
        opciones = {f"{k} · {v.split(' · ')[0]} · según día": k for k, v in self.config["turnos"].items()}
        seleccion = selecciones_del_area(nombre, area, self.config["turnos"])
        variables = []
        controles_turnos = []
        for i, lunes in enumerate(lunes_del_mes(self.mes)):
            por_defecto = "M" if (i + int(grupo.get()[-1])-1) % 2 == 0 else "T"
            if area.get("jornadas", {}).get(anterior, {}).get("tipo", "full_time") != "full_time":
                por_defecto = next(iter(self.config["turnos"]))
            turno = (seleccion_para_fecha(self.config, area, seleccion, anterior, max(lunes, self.mes))
                     if anterior else None) or por_defecto
            variable = tk.StringVar(value=next(k for k, v in opciones.items() if v == turno))
            variables.append(variable)
            ttk.Label(marco, text=f"Semana {i+1}: {lunes:%d/%m} – {lunes+timedelta(days=6):%d/%m}").grid(row=4+i, column=0, sticky="w", pady=5)
            control = ttk.Combobox(marco, textvariable=variable, values=list(opciones), state="readonly", width=36)
            control.grid(row=4+i, column=1)
            controles_turnos.append(control)
        fila = 4 + len(variables)
        encargado = tk.BooleanVar(value=anterior in area.get("encargados", {}))
        adicionales = set(area.get("encargados", {}).get(anterior, []))
        resumen = tk.StringVar(value=f"{len(adicionales)} descansos adicionales seleccionados")
        check_encargado = ttk.Checkbutton(marco, text="Encargado de turno", variable=encargado,
                        command=lambda: boton_calendario.configure(state="normal" if encargado.get() else "disabled"))
        check_encargado.grid(row=fila, column=0, sticky="w", pady=10)

        def calendario():
            popup = tk.Toplevel(ventana)
            popup.title("Días libres adicionales · Encargado")
            popup.transient(ventana)
            popup.grab_set()
            panel = ttk.Frame(popup, padding=16)
            panel.pack()
            actual = [self.mes]
            borrador = set(adicionales)
            titulo = tk.StringVar()
            ttk.Label(panel, textvariable=titulo, font=("Segoe UI", 12, "bold")).grid(row=0, column=1, columnspan=5)
            grilla = ttk.Frame(panel)
            grilla.grid(row=1, column=0, columnspan=7, pady=12)

            def pintar():
                for widget in grilla.winfo_children():
                    widget.destroy()
                titulo.set(f"{MESES[actual[0].month-1]} {actual[0].year}")
                for c, texto in enumerate(("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")):
                    ttk.Label(grilla, text=texto).grid(row=0, column=c, padx=5)
                for f, semana in enumerate(calendar.Calendar(0).monthdayscalendar(actual[0].year, actual[0].month), 1):
                    for c, numero in enumerate(semana):
                        if not numero:
                            continue
                        dia = actual[0].replace(day=numero)
                        elegido = dia.isoformat() in borrador
                        fijo = c == numero_dia(libre.get())
                        texto = f"{numero}" + (" ✓" if elegido else " F" if fijo else "")
                        ttk.Button(grilla, text=texto, width=5, command=lambda d=dia: alternar(d),
                                   state="disabled" if c == 6 or (fijo and not elegido) else "normal").grid(row=f, column=c, padx=2, pady=2)

            def alternar(dia):
                clave = dia.isoformat()
                if clave in borrador:
                    borrador.remove(clave)
                else:
                    lunes = dia - timedelta(days=dia.weekday())
                    if any((d := date.fromisoformat(v)) - timedelta(days=d.weekday()) == lunes for v in borrador):
                        messagebox.showinfo("Un adicional por semana", "Desmarca el otro descanso de esta semana antes de elegir otro día.", parent=popup)
                        return
                    borrador.add(clave)
                pintar()

            def mover(delta):
                indice = actual[0].year * 12 + actual[0].month - 1 + delta
                if not 12 <= indice < 120000:
                    return
                actual[0] = date(indice // 12, indice % 12 + 1, 1)
                pintar()

            def cerrar(aceptar=False):
                if aceptar:
                    adicionales.clear()
                    adicionales.update(borrador)
                    resumen.set(f"{len(adicionales)} descansos adicionales seleccionados")
                popup.destroy()
                ventana.grab_set()

            ttk.Button(panel, text="‹", command=lambda: mover(-1)).grid(row=0, column=0)
            ttk.Button(panel, text="›", command=lambda: mover(1)).grid(row=0, column=6)
            ttk.Label(panel, text="✓ Adicional seleccionado · F Día fijo\nMáximo uno adicional por semana. Domingos bloqueados.").grid(row=2, columnspan=7, pady=8)
            ttk.Button(panel, text="Cancelar", command=cerrar).grid(row=3, column=0, columnspan=3)
            ttk.Button(panel, text="Aceptar", command=lambda: cerrar(True)).grid(row=3, column=4, columnspan=3)
            popup.protocol("WM_DELETE_WINDOW", cerrar)
            pintar()

        boton_calendario = ttk.Button(marco, text="Elegir días libres…", command=calendario,
                                     state="normal" if encargado.get() else "disabled")
        boton_calendario.grid(row=fila, column=1, sticky="e")
        ttk.Label(marco, textvariable=resumen).grid(row=fila+1, columnspan=2, sticky="w")
        fila += 2
        ttk.Label(marco, text="Consulta las horas por día en Administrar turnos.\nSe aplica la reducción semanal cuando corresponda.").grid(row=fila, columnspan=2, pady=12)

        panel_jornada = ttk.LabelFrame(marco, text="Tipo de jornada", padding=12)
        panel_jornada.grid(row=0, column=2, rowspan=fila+2, sticky="ns", padx=(18, 0))
        jornada_actual = area.get("jornadas", {}).get(anterior, {"tipo": "full_time"})
        tipos = {"Full time": "full_time", "Part time 30 h": "part_time_30", "Part time 20 h": "part_time_20"}
        tipo_var = tk.StringVar(value=next(k for k, v in tipos.items() if v == jornada_actual["tipo"]))
        selector_tipo = ttk.Combobox(panel_jornada, textvariable=tipo_var, values=list(tipos), state="readonly", width=23)
        selector_tipo.grid(row=0, columnspan=3, sticky="ew", pady=(0, 12))
        ttk.Label(panel_jornada, text="Días trabajados cada semana").grid(row=1, columnspan=3, sticky="w")
        seleccion_dias, entradas_pt, controles_dias, controles_entradas = [], [], [], []
        salidas_pt = []
        for i, dia in enumerate(DIAS_COMPLETOS):
            elegido = tk.BooleanVar(value=i in jornada_actual.get("dias", []))
            hora = tk.StringVar(value=jornada_actual.get("entradas", {}).get(str(i), "09:00"))
            salida = tk.StringVar()
            check = ttk.Checkbutton(panel_jornada, text=dia.capitalize(), variable=elegido)
            check.grid(row=2+i, column=0, sticky="w", pady=4)
            entry = ttk.Entry(panel_jornada, textvariable=hora, width=7)
            entry.grid(row=2+i, column=1, padx=5)
            ttk.Label(panel_jornada, textvariable=salida).grid(row=2+i, column=2)
            seleccion_dias.append(elegido)
            entradas_pt.append(hora)
            controles_dias.append(check)
            controles_entradas.append(entry)
            salidas_pt.append(salida)
        ayuda_jornada = tk.StringVar()
        ttk.Label(panel_jornada, textvariable=ayuda_jornada, wraplength=255).grid(row=9, columnspan=3, sticky="w", pady=12)
        opciones_domingo = {"Turno de la semana": "", "Mañana": "M", "Tarde": "T"}
        domingo_var = tk.StringVar(value=next(k for k, v in opciones_domingo.items()
                                              if v == area.get("domingo_turno", {}).get(anterior, "")))
        ttk.Label(panel_jornada, text="Turno del domingo trabajado").grid(row=10, columnspan=3, sticky="w", pady=(10, 4))
        selector_domingo = ttk.Combobox(panel_jornada, textvariable=domingo_var,
                                       values=list(opciones_domingo), state="readonly", width=23)
        selector_domingo.grid(row=11, columnspan=3, sticky="ew")
        ttk.Label(panel_jornada, text="No cambia los domingos libres. En PT20 se conserva la entrada elegida.", wraplength=255).grid(row=12, columnspan=3, sticky="w", pady=8)

        def actualizar_jornada(*_):
            tipo = tipos[tipo_var.get()]
            full = tipo == "full_time"
            selector_domingo.configure(state="disabled" if tipo == "part_time_20" else "readonly")
            for c in controles_full:
                c.configure(state="readonly" if full else "disabled")
            check_encargado.configure(state="normal" if full else "disabled")
            boton_calendario.configure(state="normal" if full and encargado.get() else "disabled")
            for c in controles_turnos:
                c.configure(state="disabled" if tipo == "part_time_20" else "readonly")
            for i in range(7):
                controles_dias[i].configure(state="disabled" if full else "normal")
                activo = tipo == "part_time_20" and seleccion_dias[i].get()
                controles_entradas[i].configure(state="normal" if activo else "disabled")
                valor = entradas_pt[i].get()
                if activo and re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", valor):
                    minutos = int(valor[:2])*60 + int(valor[3:]) + 630
                    salidas_pt[i].set(f"→ {minutos//60%24:02d}:{minutos%60:02d}" + (" +1" if minutos >= 1440 else ""))
                else:
                    salidas_pt[i].set("")
            ayuda_jornada.set({
                "full_time": "Día libre fijo y domingo por medio. Máximo 45 h semanales.",
                "part_time_30": "Elige 4 días. Usa los turnos semanales de la izquierda, sin reducción. Máximo 32 h. El domingo se repite si lo seleccionas.",
                "part_time_20": "Elige 2 días e indica la entrada HH:MM. Cada día dura 10 h 30 min: total 21 h. +1 indica salida al día siguiente. El domingo seleccionado se trabaja siempre.",
            }[tipo])
        selector_tipo.bind("<<ComboboxSelected>>", actualizar_jornada)
        for v in seleccion_dias + entradas_pt:
            v.trace_add("write", actualizar_jornada)
        actualizar_jornada()

        def aplicar():
            try:
                tipo = tipos[tipo_var.get()]
                jornada = {"tipo": tipo}
                if tipo != "full_time":
                    jornada["dias"] = [i for i, v in enumerate(seleccion_dias) if v.get()]
                if tipo == "part_time_20":
                    jornada["entradas"] = {str(i): entradas_pt[i].get().strip() for i in jornada["dias"]}
                self.config = guardar_persona(self.config, nombre, anterior, persona.get(), libre.get(),
                                               int(grupo.get()[-1])-1, self.mes, [opciones[v.get()] for v in variables],
                                               encargado=encargado.get(), adicionales=adicionales, jornada=jornada,
                                               domingo_turno=opciones_domingo[domingo_var.get()])
                self.marcar()
                self.refrescar()
                ventana.destroy()
            except ValueError as error:
                messagebox.showerror("Revisa los datos", str(error), parent=ventana)
        ttk.Button(marco, text="Aplicar cambios", command=aplicar).grid(row=fila+1, column=1, sticky="e")
        ttk.Button(marco, text="Cancelar", command=ventana.destroy).grid(row=fila+1, column=0, sticky="w")

    def eliminar(self, nombre):
        tabla = self.tablas[nombre]
        if not tabla.selection():
            return
        area = self.config["areas"][nombre]
        persona = area["empleados"][int(tabla.selection()[0])]
        if not messagebox.askyesno("Eliminar persona", f"¿Eliminar a {persona} y sus turnos guardados?", parent=self.root):
            return
        grupos = area.setdefault("domingo_grupo", {})
        for i, e in enumerate(area["empleados"]):
            grupos.setdefault(e, i % 2)
        area["empleados"].remove(persona)
        for mapa in [area["dias_libres"], grupos, area.get("encargados", {}), area.get("jornadas", {}), area.get("domingo_turno", {})] + list(area.get("turnos_semanales", {}).values()) + list(area.get("turnos_por_mes", {}).values()):
            mapa.pop(persona, None)
        self.marcar()
        self.refrescar()

    def editar_turnos(self):
        ventana, marco = self.dialogo("Administrar turnos")
        seleccion = tk.StringVar(value="Nuevo turno")
        selector = ttk.Combobox(marco, textvariable=seleccion,
                                values=["Nuevo turno"] + list(self.config["turnos"]), state="readonly")
        selector.grid(row=0, column=1, columnspan=2, sticky="ew", pady=6)
        ttk.Label(marco, text="Crear o editar").grid(row=0, column=0, sticky="w")
        codigo, nombre = tk.StringVar(), tk.StringVar()
        ttk.Label(marco, text="Código").grid(row=1, column=0, sticky="w")
        entrada_codigo = ttk.Entry(marco, textvariable=codigo, width=14)
        entrada_codigo.grid(row=1, column=1, sticky="w", pady=6)
        ttk.Label(marco, text="Nombre").grid(row=2, column=0, sticky="w")
        ttk.Entry(marco, textvariable=nombre, width=30).grid(row=2, column=1, columnspan=2, sticky="ew", pady=6)
        ttk.Label(marco, text="Entrada (HH:MM)").grid(row=3, column=1, padx=8)
        ttk.Label(marco, text="Salida (HH:MM)").grid(row=3, column=2, padx=8)
        horas = []
        for i, dia in enumerate(DIAS_COMPLETOS):
            ttk.Label(marco, text=dia.capitalize()).grid(row=4+i, column=0, sticky="w", padx=(0, 16))
            par = [tk.StringVar(value="09:00"), tk.StringVar(value="17:00")]
            horas.append(par)
            for c, v in enumerate(par, 1):
                ttk.Entry(marco, textvariable=v, width=12).grid(row=4+i, column=c, padx=8, pady=4)
        reduccion = tk.StringVar(value="Salir una hora antes")
        opciones = {"Salir una hora antes": "salida", "Entrar una hora después": "entrada"}
        ttk.Label(marco, text="Reducción semanal").grid(row=11, column=0, sticky="w", pady=10)
        ttk.Combobox(marco, textvariable=reduccion, values=list(opciones), state="readonly", width=29).grid(row=11, column=1, columnspan=2)
        ttk.Label(marco, text="Si la salida es anterior a la entrada, termina al día siguiente.\nEl código de un turno existente se conserva para mantener sus asignaciones.").grid(row=12, columnspan=3, pady=10)

        def cargar(_=None):
            clave = seleccion.get()
            existente = clave != "Nuevo turno"
            entrada_codigo.configure(state="normal")
            codigo.set(clave if existente else "")
            nombre.set(self.config["turnos"][clave].split(" · ")[0] if existente else "")
            for i, par in enumerate(horas):
                texto = horario_del_dia(self.config, clave, date(2026, 9, 28)+timedelta(days=i)) if existente else "09:00 a 17:00"
                valores = re.findall(r"\b(?:[01]\d|2[0-3]):[0-5]\d\b", texto)
                for v, valor in zip(par, valores if len(valores) == 2 else ["", ""]):
                    v.set(valor)
            regla = self.config.get("turnos_detalle", {}).get(clave, {}).get("reduccion", "entrada" if clave == "T" else "salida")
            reduccion.set(next(k for k, v in opciones.items() if v == regla))
            if existente:
                entrada_codigo.configure(state="readonly")

        def aplicar():
            try:
                self.config = guardar_turno(self.config, codigo.get(), nombre.get(),
                                            [[v.get().strip() for v in par] for par in horas],
                                            opciones[reduccion.get()], seleccion.get() != "Nuevo turno")
                self.marcar()
                self.refrescar()
                ventana.destroy()
            except ValueError as error:
                messagebox.showerror("Revisa el turno", str(error), parent=ventana)
        selector.bind("<<ComboboxSelected>>", cargar)
        ttk.Button(marco, text="Cancelar", command=ventana.destroy).grid(row=13, column=0)
        ttk.Button(marco, text="Aplicar turno", command=aplicar).grid(row=13, column=2)

    def cobertura(self, nombre):
        ventana, marco = self.dialogo(f"Cobertura mínima · {nombre}")
        area = self.config["areas"][nombre]
        variables = {}
        ttk.Label(marco, text="Personas mínimas necesarias por turno").grid(row=0, columnspan=3, pady=(0, 12))
        ttk.Label(marco, text="Lunes a sábado").grid(row=1, column=1)
        ttk.Label(marco, text="Domingos").grid(row=1, column=2)
        for fila, (turno, descripcion) in enumerate(self.config["turnos"].items(), 2):
            ttk.Label(marco, text=descripcion).grid(row=fila, column=0, padx=(0, 15), pady=8)
            for columna, clave in enumerate(("cobertura", "cobertura_domingo"), 1):
                v = tk.StringVar(value=str(area.get(clave, area["cobertura"]).get(turno, 0)))
                variables[clave, turno] = v
                ttk.Spinbox(marco, from_=0, to=100, width=7, textvariable=v).grid(row=fila, column=columna, padx=8)

        def aplicar():
            try:
                valores = {k: int(v.get()) for k, v in variables.items()}
                if any(v < 0 for v in valores.values()):
                    raise ValueError
            except ValueError:
                messagebox.showerror("Cantidad inválida", "Usa números enteros desde cero.", parent=ventana)
                return
            for clave in ("cobertura", "cobertura_domingo"):
                area[clave] = {t: valores[clave, t] for t in self.config["turnos"]}
            self.marcar()
            ventana.destroy()
        ttk.Button(marco, text="Aplicar", command=aplicar).grid(row=len(self.config["turnos"])+2, column=2, pady=12)

    def guardar(self):
        try:
            validar(self.config)
            temporal = self.ruta.with_suffix(".tmp")
            temporal.write_text(json.dumps(self.config, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
            temporal.replace(self.ruta)
            self.modificado = False
            self.estado.set("Configuración guardada.")
            return True
        except (ValueError, OSError) as error:
            messagebox.showerror("No se pudo guardar", str(error), parent=self.root)
            return False

    def calcular(self):
        try:
            return generar_mes(self.config, self.mes)
        except ValueError as error:
            messagebox.showerror("Revisa los turnos y la cobertura", str(error), parent=self.root)
            return None

    def previa(self):
        resultado = self.calcular()
        if resultado is None:
            return
        fechas, horarios = resultado
        ventana = tk.Toplevel(self.root)
        ventana.title(f"Vista previa · {MESES[self.mes.month-1]} {self.mes.year}")
        ventana.geometry("900x600")
        texto = tk.Text(ventana, wrap="none", font=("Consolas", 11), padx=16, pady=16)
        sy = ttk.Scrollbar(ventana, command=texto.yview)
        sy.pack(side="right", fill="y")
        sx = ttk.Scrollbar(ventana, orient="horizontal", command=texto.xview)
        sx.pack(side="bottom", fill="x")
        texto.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        texto.pack(fill="both", expand=True)
        texto.insert("end", "\n".join(f"{t}: {d}" for t, d in self.config["turnos"].items())+"\nLIBRE: descanso\n\n")
        texto.insert("end", "Las casillas muestran los horarios por día y la reducción semanal aplicada.\n\n")
        for area, empleados in horarios.items():
            for persona, turnos in empleados.items():
                texto.insert("end", f"{area} · {persona}\n")
                texto.insert("end", "".join(f"{d.capitalize():<42}" for d in DIAS_COMPLETOS)+"Total semanal\n")
                for semana in calendar.Calendar(0).monthdayscalendar(self.mes.year, self.mes.month):
                    total = next(turnos[d-1].horas_semana for d in semana if d)
                    texto.insert("end", "".join(f"{str(d)+' '+descripcion_turno(self.config, turnos[d-1]) if d else '':<42}" for d in semana)+f"{total:g} h\n")
                texto.insert("end", "\n")
        texto.configure(state="disabled")

    def generar(self):
        resultado = self.calcular()
        if resultado is None:
            return
        alertas = evaluar_cobertura(self.config, self.mes)
        if any(a["presentes"] == 0 for a in alertas):
            self.actualizar_alertas()
            messagebox.showerror("Hay horarios sin personal", "Revisa las alertas rojas del panel. No se puede exportar mientras haya tramos sin personal dentro de los horarios requeridos.", parent=self.root)
            return
        ruta = filedialog.asksaveasfilename(parent=self.root, title="Guardar Excel de horarios", defaultextension=".xlsx",
                                            filetypes=[("Libro de Excel", "*.xlsx")], initialfile=f"horarios_{self.mes:%Y-%m}.xlsx")
        if not ruta:
            return
        try:
            if Path(ruta).suffix.lower() != ".xlsx":
                raise ValueError("El nombre debe terminar en .xlsx.")
            exportar(self.config, *resultado, Path(ruta))
            self.ultimo_excel = ruta
            self.estado.set(f"Excel generado: {ruta}" + (" · Hay cambios sin guardar." if self.modificado else ""))
            messagebox.showinfo("Excel generado", "El horario está listo. Puedes abrirlo con «Abrir último Excel».", parent=self.root)
        except FileExistsError:
            messagebox.showerror("El archivo ya existe", "Elige otro nombre para proteger el Excel existente.", parent=self.root)
        except (ValueError, OSError) as error:
            messagebox.showerror("No se pudo exportar", str(error), parent=self.root)

    def abrir_excel(self):
        if not self.ultimo_excel:
            messagebox.showinfo("Sin archivo", "Primero genera un Excel.", parent=self.root)
            return
        try:
            os.startfile(self.ultimo_excel)
        except OSError as error:
            messagebox.showerror("No se pudo abrir", str(error), parent=self.root)

    def cerrar(self):
        if self.modificado:
            respuesta = messagebox.askyesnocancel("Cambios sin guardar", "¿Guardar los cambios antes de salir?", parent=self.root)
            if respuesta is None or (respuesta and not self.guardar()):
                return
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        Aplicacion(root)
    except (ValueError, OSError) as error:
        root.withdraw()
        messagebox.showerror("No se pudo iniciar", f"Revisa configuracion.json:\n\n{error}", parent=root)
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
