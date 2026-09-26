# Horarios rotativos

Programa simple para Python 3.10 o superior. No necesita instalar librerías.
Genera un Excel `.xlsx` con una hoja para Cocina, otra para Barra y otra para
Garzones. Debajo del nombre de cada trabajador aparece su calendario mensual,
con columnas de lunes a domingo. Cada casilla muestra el día del mes y la
descripción del turno o `LIBRE`; los días ajenos al mes quedan vacíos.

## Uso

1. Edita `configuracion.json` con los nombres y turnos de tu empresa.
2. En Windows, haz doble clic en `generar.vbs` para abrir la interfaz gráfica sin consola.
3. Elige el mes y pulsa **Mostrar mes**. Edita las personas y pulsa **Generar Excel…** para elegir dónde guardarlo.
4. Revisa la vista previa de impresión y selecciona todo el libro para imprimir las tres áreas.

También puedes elegir el mes y archivo desde una terminal:

```powershell
python horarios.py --mes 2026-10 --salida salidas/octubre.xlsx
```

Si el archivo ya existe, el programa pide usar otro nombre para proteger cambios manuales.

## Interfaz para Windows

También puedes abrirla con `python interfaz.py`. Utiliza tkinter, incluido en
la instalación habitual de Python para Windows; no requiere paquetes externos.

Para abrir únicamente la ventana de la aplicación, utiliza `generar.vbs`, que
inicia Python con `pythonw.exe` (o `pyw.exe` si está disponible como alternativa).
Puedes crear un acceso directo a ese archivo. `generar.bat` se mantiene por
compatibilidad, pero Windows puede mostrar brevemente CMD al ejecutar un `.bat`.

- Las pestañas separan Cocina, Barra y Garzones.
- Haz doble clic en una persona para editar su nombre, día libre, grupo de
  domingos y turno de cada semana. Las fechas de cada semana aparecen junto
  al selector. Elige un turno concreto para cada semana.
- **Agregar persona** y **Eliminar** actualizan también las asignaciones guardadas.
- **Cobertura mínima** permite ajustar por separado lunes a sábado y domingos.
- **Guardar cambios** (Ctrl+S) conserva la configuración para futuras sesiones.
- **Vista previa** muestra el calendario calculado, incluidos todos los descansos.
- **Generar Excel…** exporta los cambios actuales y **Abrir último Excel** abre
  el archivo con la aplicación asociada en Windows. Exportar no guarda la configuración.

Las semanas compartidas entre meses se actualizan juntas. La interfaz conserva
los grupos dominicales al renombrar o eliminar personas. Antes de exportar se
comprueba la cobertura; si hay conflictos, se indican para que puedas corregirlos.
Al cerrar con cambios pendientes puedes guardarlos, descartarlos o seguir editando.

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

## Alertas de cobertura por hora

El panel derecho se actualiza al aplicar cambios de personas, turnos, descansos,
grupos dominicales o cobertura, y al mostrar otro mes. Evalúa la presencia real
después de reducir horas, incluidos los turnos nocturnos. Comprueba cada hora
y también cambios a minutos intermedios (por ejemplo 10:30).

El horario requerido se deduce de los turnos con cobertura mínima positiva.
Cuando se solapan varios turnos, se suman sus mínimos. Se cuenta toda persona
presente del área, independientemente del código de su turno. No se exige
personal fuera de esos horarios; configura la cobertura para representar todas
las horas en que el área debe estar atendida.

Cada alerta indica área, fecha, tramo, personas presentes y mínimo requerido.
Los tramos sin personal aparecen en rojo y bloquean la exportación desde la
interfaz; los déficits con al menos una persona se muestran como advertencias.
La vista previa sigue disponible para revisar y corregir los horarios.
Se incluye la madrugada del primer día y el cierre nocturno del último día.
Las alertas se calculan sin guardar los cambios en disco.

## Agregar y editar turnos

Pulsa **Administrar turnos** en la barra superior. Elige **Nuevo turno** o el
código de uno existente. Define el nombre, entrada y salida para cada día de
lunes a domingo y cómo descontar la hora semanal: salir antes o entrar después.
Usa formato `HH:MM`. Si la salida es anterior a la entrada, corresponde al día
siguiente. Pulsa **Aplicar turno** y después **Guardar cambios**.

Los nuevos turnos aparecen en los selectores semanales y en **Cobertura mínima**,
con mínimo cero inicialmente. Las ediciones se aplican a todas las asignaciones
del código, incluidos otros meses, sin cambiar la selección de cada trabajador.
El código existente no se renombra. Los horarios editados por día reemplazan las
variaciones predeterminadas de mañana y tarde. El límite de 45 horas sigue vigente.

## Rotación al cambiar de mes

### Turno del domingo trabajado

Al crear o editar una persona, el selector **Turno del domingo trabajado** permite
elegir **Mañana**, **Tarde** o **Turno de la semana**. Se aplica a todos sus domingos
trabajados, sin cambiar los domingos libres ni los turnos de lunes a sábado.
La selección tiene prioridad sobre la rotación mensual y el turno semanal.
Usa las horas dominicales del turno, incluidas las ediciones de Administrar turnos.

También está disponible para part time de 30 h si trabaja domingo. Para part time
de 20 h está deshabilitada, pues se conserva su entrada personalizada y duración
de 10 h 30 min. Guarda los cambios para conservar la elección; el panel de alertas
se actualiza al aplicarla. En JSON se guarda como `"domingo_turno": {"Ana": "M"}`.

La opción «Automático» ya no aparece en el editor de personas. Para full time,
las semanas sin elección manual del mes usan el grupo dominical: grupo 1 empieza
con mañana y sigue tarde, mañana…; grupo 2 empieza tarde y sigue mañana, tarde…
La semana 1 es la primera fila del calendario, aunque sea parcial. La rotación
se reinicia el día 1 de cada mes y no modifica la alternancia de domingos libres.
Una semana que cruza de mes puede cambiar de turno al comenzar el nuevo mes.
Las selecciones manuales del mes se conservan. Puedes editar los turnos propuestos.

La regla no cambia los part time: conservan sus días y horarios. Un part time
de 30 h sin selección se muestra como «Sin selección»; al editarlo, elige sus
turnos semanales. Las alertas siguen evaluando los huecos que cause la rotación.

## Tipos de jornada

Al crear o editar una persona, el panel **Tipo de jornada** permite elegir:

- **Full time:** reglas actuales, con día libre fijo, domingos alternados y
  máximo de 45 horas. Puede tener descansos adicionales como encargado.
- **Part time 30 h:** elige exactamente cuatro días de la semana. Usa los turnos
  semanales existentes, sin descuentos de horas por trabajar domingo. Se valida
  un máximo de **32 horas semanales**; puede sumar menos según los turnos elegidos.
- **Part time 20 h:** elige exactamente dos días e indica la entrada de cada uno
  en formato HH:MM. La salida se calcula 10 h 30 min después. Son **21 horas por
  semana**, según la duración solicitada; no se usan los selectores semanales.

En part time los días seleccionados se repiten todas las semanas, incluido el
domingo si está marcado. Los demás días aparecen como `LIBRE`. No se aplican el
día libre fijo, los grupos dominicales ni los descansos adicionales de encargado.
Las horas reales se reflejan en la vista previa, el Excel y las alertas de cobertura.
Los cambios de jornada afectan también los meses ya configurados.
Las personas existentes se consideran full time hasta que cambies su jornada.

## Encargados de turno

En **Agregar persona** o **Editar selección**, marca **Encargado de turno**.
El botón **Elegir días libres…** abre un mini calendario con navegación por mes.
Haz clic para seleccionar o quitar un descanso adicional: se indica con ✓.
El día libre fijo aparece con F. Los domingos están bloqueados y mantienen su
alternancia habitual. Puedes añadir como máximo un descanso adicional por semana
de lunes a sábado, distinto del día fijo, también en semanas compartidas entre meses.

Las fechas adicionales se eligen individualmente; no se repiten automáticamente.
Pulsa **Aceptar**, **Aplicar cambios** y **Guardar cambios** para conservarlas.
Al desmarcar **Encargado de turno** y aplicar, se eliminan sus descansos adicionales.
Los encargados pueden tener dos descansos de lunes a sábado más su domingo libre
cuando corresponda. Si falta personal para cubrir los turnos, la exportación
informa el conflicto sin quitar descansos. En Excel se muestran como `LIBRE`.

En la configuración, se guardan por área como
`"encargados": {"Ana": ["2026-09-30", "2026-10-09"]}`.
Una lista vacía identifica a un encargado que todavía no tiene días adicionales.

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
selección full time usan la rotación mensual según su grupo de domingos.

También se mantiene la opción `turnos_semanales` por fecha exacta del lunes:

```json
"turnos_semanales": {
  "2026-09-28": {"Ana": "M", "Luis": "T"},
  "2026-10-05": {"Ana": "I", "Luis": "M"}
}
```

La persona tendrá ese turno salvo su día fijo y el domingo que le toque descansar.
Quienes no tengan selección completan los mínimos y también reciben turno en los
días restantes. Para full time, `{}` activa la rotación mensual por grupo.
Las selecciones no se repiten en semanas futuras: agrega el lunes de cada semana.

La cobertura indica cantidades **mínimas**, que pueden superarse. Puedes elegir
intermedio aunque su mínimo sea cero si quedan personas para cubrir los demás
turnos. Para exigir intermedio, incrementa `I` en la cobertura correspondiente.
Si una selección impide cubrir los mínimos, se informa el área y la fecha.

## Máximo semanal de 45 horas

Los horarios base dependen del día:

| Turno | Lunes a miércoles | Jueves y viernes | Sábado | Domingo |
| --- | --- | --- | --- | --- |
| Mañana | 09:00–17:00 | 09:00–17:00 | 10:30–18:30 | 10:00–18:00 |
| Tarde | 16:00–00:00 | 18:00–02:00 del día siguiente | 18:00–02:00 del día siguiente | 14:00–22:00 |
| Intermedio | 13:00–19:00 | 13:00–19:00 | 13:00–19:00 | 13:00–19:00 |

El turno nocturno pertenece al día en que empieza y cuenta como 8 horas.
Las variantes de sábado, domingo y tarde de jueves a sábado se aplican
automáticamente al código elegido, antes de descontar horas.

La semana se calcula de lunes a domingo, incluyendo los días del mes vecino
cuando corresponda. En semanas con domingo trabajado se descuenta una hora
en los tres primeros días trabajados, saltando los descansos:

- Mañana: salida una hora antes del horario correspondiente al día.
- Tarde: entrada una hora después del horario correspondiente al día
  (por ejemplo, jueves reducido: 19:00–02:00).
- Intermedio: salida a las 18:00 en vez de las 19:00.

Los otros días conservan sus horas habituales. Seis turnos de 8 horas quedan
en 45 horas; los turnos intermedios y los descansos adicionales pueden dejar
un total menor. No se agregan horas para llegar a 45. Con domingo libre no se
aplica esta reducción. La vista previa muestra las horas efectivas y los totales
semanales. El Excel muestra los horarios sin aclaraciones de día siguiente ni
totales semanales ni nombres de turno: solo fecha y horas (por ejemplo
`18:00 – 02:00`) o `LIBRE`, para simplificar la impresión. Si se superan 45 horas, se bloquea
la generación y se informa la persona y semana afectadas.

Las horas se calculan entre entrada y salida, sin descontar pausas. La cobertura
sigue definiéndose por turno; el panel contrasta esos mínimos con las personas
presentes en cada franja, después de reducir las jornadas.

## Ciclo base

Primero se respetan los descansos y selecciones semanales; después se cubren
los mínimos. Las personas adicionales reciben turnos con cobertura positiva,
con una prioridad que rota semanalmente. No se garantiza igualdad de turnos.
Cada persona tiene como máximo un turno por día. Cambiar la configuración
puede modificar resultados para fechas ya exportadas.

Esta versión no contempla vacaciones, ausencias, otras restricciones de disponibilidad,
descansos mínimos entre turnos ni otras reglas de jornada. Revisa esos requisitos
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
