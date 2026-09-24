# Horarios rotativos

Programa simple para Python 3.10 o superior. No necesita instalar librerías.
Genera un Excel `.xlsx` con una hoja para Cocina, otra para Barra y otra para
Garzones. Debajo del nombre de cada trabajador aparece su calendario mensual,
con columnas de lunes a domingo. Cada casilla muestra el día del mes y la
descripción del turno o `LIBRE`; los días ajenos al mes quedan vacíos.

## Uso

1. Edita `configuracion.json` con los nombres y turnos de tu empresa.
2. En Windows, haz doble clic en `generar.bat`: genera el mes actual completo.
3. Abre el archivo en la carpeta `salidas` con Excel o LibreOffice.
4. Revisa la vista previa de impresión y selecciona todo el libro para imprimir las tres áreas.

También puedes elegir el mes y archivo desde una terminal:

```powershell
python horarios.py --mes 2026-10 --salida salidas/octubre.xlsx
```

Si el archivo ya existe, el programa pide usar otro nombre para proteger cambios manuales.

El archivo predeterminado se llama `salidas/horarios_AAAA-MM.xlsx`.
Se incluyen todos los días del mes, incluso los anteriores a hoy. La rotación
y los días libres fijos se conservan entre meses.

Para un período personalizado sigue disponible
`python horarios.py --inicio 2026-09-28 --semanas 4`.
Se separa en calendarios por mes, marcando las fechas no incluidas como
`Fuera del período`. No se puede combinar `--mes` con `--inicio` o `--semanas`.

## Configuración y rotación

- `empresa`: título del documento.
- `inicio_rotacion`: fecha de referencia del ciclo. Conserva esta fecha entre exportaciones para mantener la continuidad.
- `turnos`: códigos y descripciones de los turnos, en el orden de rotación deseado. Las horas se muestran como texto.
- `empleados`: lista ordenada de personas de cada área.
- `cobertura`: mínimo de personas por turno; las personas adicionales también trabajan.
- `desfase`: adelanta el ciclo del área el número de días indicado; normalmente puedes dejarlo en cero.
- `dias_libres`: día libre fijo obligatorio de cada persona, de lunes a sábado.

## Elegir un día libre por persona

En cada área de `configuracion.json`, edita `dias_libres`, usando exactamente
los nombres de la lista `empleados`. Por ejemplo, en Cocina:

```json
"dias_libres": {
  "Ana": "lunes",
  "Luis": "martes",
  "Carla": "miércoles",
  "Pedro": "jueves"
}
```

Cada persona debe tener un día fijo de lunes a sábado: será su único descanso
entre esos días. Además, tendrá un domingo libre y el siguiente trabajado.
Alternará semanas con dos descansos y con uno; todos los demás días tendrán turno.

Por defecto, las posiciones 1, 3, 5 de empleados descansan el domingo de la semana
de `inicio_rotacion`; las posiciones 2, 4, 6 descansan el siguiente. Puedes elegir
el grupo dentro del área: `"domingo_grupo": {"Ana": 0, "Luis": 1}`. El grupo 0
descansa en la semana de referencia y el 1 en la siguiente. Para personas omitidas
se utiliza su posición. La alternancia continúa entre meses y años: conserva la
fecha de referencia, el orden de empleados y los grupos para mantenerla.

Puedes definir `cobertura_domingo` con mínimos distintos para domingos; si no
existe se usa `cobertura`. En el ejemplo, Garzones tiene tres personas disponibles
cada domingo: se exige una de mañana y una de tarde, y la tercera también recibe
turno. Si no alcanza la dotación, el programa informa el conflicto sin modificar
descansos ni generar el Excel.

## Elegir turnos por semana

Los tres turnos disponibles son `M` (mañana, 09:00 a 17:00), `T` (tarde,
16:00 a 00:00, medianoche al terminar el día) e `I` (intermedio, 13:00 a 19:00).
Dentro de cada área, usa `turnos_por_mes` para elegir un turno por trabajador
para cada semana del calendario mensual:

```json
"turnos_por_mes": {
  "2026-09": {
    "Ana": ["M", "T", "M", "T", "M"],
    "Luis": ["M", "T", "M", "T", "M"],
    "Carla": ["T", "M", "T", "M", "T"],
    "Pedro": ["T", "M", "T", "M", "T"]
  }
}
```

Cada posición corresponde a una fila del calendario: semana 1, 2, 3, etc.
La primera contiene el día 1, aunque empiece en el mes anterior. En septiembre
de 2026 las semanas comienzan el 31 de agosto y el 7, 14, 21 y 28 de septiembre.
Incluye 4, 5 o 6 turnos según las filas del mes; el programa indica la cantidad
necesaria si la lista no coincide. Los valores permitidos son `M`, `T` e `I`.

**El turno seleccionado es fijo durante toda la semana, de lunes a domingo.**
Solo se sustituye por `LIBRE` en el día fijo o el domingo que corresponda.
Si la cobertura es incompatible, el programa informa el conflicto; no cambia
el turno elegido para cubrir faltantes. La alternancia dominical no se reinicia.

Las semanas compartidas por dos meses conservan el mismo turno. Si configuras
ambos meses, la última selección de uno y la primera del siguiente deben coincidir
cuando compartan una semana. El programa rechaza selecciones contradictorias.

La configuración incluida ya trae septiembre de 2026 para todos los trabajadores.
Agrega otros meses y personas con el mismo formato. Las personas o semanas sin
selección usan asignación automática, que puede cambiar de turno entre días.

También se mantiene la opción `turnos_semanales` por fecha exacta del lunes:

```json
"turnos_semanales": {
  "2026-09-28": {"Ana": "M", "Luis": "T"},
  "2026-10-05": {"Ana": "I", "Luis": "M"}
}
```

La persona tendrá ese turno salvo su día fijo y el domingo que le toque descansar.
Quienes no tengan selección completan los mínimos y también reciben turno en los
días restantes. Usa `{}` para mantener la asignación automática.
Las selecciones no se repiten en semanas futuras: agrega el lunes de cada semana.

La cobertura indica cantidades **mínimas**, que pueden superarse. Puedes elegir
intermedio aunque su mínimo sea cero si quedan personas para cubrir los demás
turnos. Para exigir intermedio, incrementa `I` en la cobertura correspondiente.
Si una selección impide cubrir los mínimos, se informa el área y la fecha.

## Ciclo base

Primero se respetan los descansos y selecciones semanales; después se cubren
los mínimos. Las personas adicionales reciben turnos con cobertura positiva,
con una prioridad que rota semanalmente. No se garantiza igualdad de turnos.
Cada persona tiene como máximo un turno por día. Cambiar la configuración
puede modificar resultados para fechas ya exportadas.

Esta versión no contempla vacaciones, ausencias, otras restricciones de disponibilidad,
límites de horas ni descansos mínimos entre turnos. Revisa esos requisitos
antes de usar el horario definitivo. Los nombres y horas incluidos son ejemplos.

El formato usa papel A4 vertical, colores suaves y dos trabajadores por página,
cada uno con su mes completo, siguiendo la organización de la imagen de
referencia. Incluye saltos de página entre pares de trabajadores y entre meses.
Revisa la vista previa en Excel según tu impresora; descripciones de turnos
muy largas pueden requerir aumentar el alto de las filas.

## Verificación

```powershell
python -m unittest discover -s tests -v
```
