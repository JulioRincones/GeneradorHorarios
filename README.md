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
- `cobertura`: cantidad de personas necesarias **cada día** por turno y área.
- `desfase`: adelanta el ciclo del área el número de días indicado; normalmente puedes dejarlo en cero.
- `dias_libres`: día libre fijo semanal de cada persona (opcional).

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

Ana tendrá libre todos los lunes, Luis todos los martes, y así sucesivamente
durante todas las semanas exportadas. Puedes elegir de lunes a domingo;
se aceptan mayúsculas y nombres con o sin tilde. Para dejar a alguien sin día
fijo, elimina su entrada. Para desactivar esta opción en un área, usa `{}`.

Los descansos se muestran como `LIBRE` en el Excel. Puede haber días libres
adicionales según la cobertura. El programa reasigna los turnos que coincidan
con un descanso fijo a personas disponibles, manteniendo la cobertura diaria.
Si no es posible cubrirla, indica el área y día del conflicto y no genera el
archivo. Con descansos fijos, la cantidad de turnos por persona puede variar.

## Elegir turnos por semana

Los tres turnos disponibles son `M` (mañana, 09:00 a 17:00), `T` (tarde,
16:00 a 00:00, medianoche al terminar el día) e `I` (intermedio, 13:00 a 19:00).
Dentro de cada área, cambia `turnos_semanales` para elegir un turno por persona
desde el lunes indicado hasta el domingo, incluso si la semana cruza de mes:

```json
"turnos_semanales": {
  "2026-09-28": {"Ana": "M", "Luis": "T"},
  "2026-10-05": {"Ana": "I", "Luis": "M"}
}
```

La persona tendrá ese turno todos los días de esa semana salvo su día libre
fijo. Quienes no tengan selección completan la cobertura automáticamente y
pueden tener descansos adicionales. Usa `{}` para mantener la rotación automática.
Las selecciones no se repiten en semanas futuras: agrega el lunes de cada semana.

La cobertura sigue indicando la cantidad **exacta** de personas por turno.
El intermedio comienza con `"I": 0`; para usarlo en Cocina, por ejemplo, cambia
la cobertura a `{"M": 1, "T": 1, "I": 1}`. Si una selección supera la cobertura
o impide cubrirla, el programa indica el área y la fecha, sin generar el Excel.

## Ciclo base

Sin días libres fijos, Cocina y Barra tienen cuatro personas y dos puestos diarios:
cada persona repite el ciclo mañana, tarde, libre, libre, empezando en un punto
distinto. Garzones tiene seis personas y cuatro puestos diarios: mañana,
mañana, tarde, tarde, libre, libre. En un ciclo completo todos pasan por la
misma cantidad de cada turno y de días libres. En períodos parciales puede
haber una diferencia. Cada persona tiene como máximo un turno por día.

La cobertura se mantiene igual de lunes a domingo. Si hay más puestos que
personas, el programa informa el error; si hay tantos puestos como personas,
no habrá días libres. Cambiar el orden de empleados, la cobertura o los turnos
cambia el ciclo, incluso para fechas ya exportadas.

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
