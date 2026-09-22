# Horarios rotativos

Programa simple para Python 3.10 o superior. No necesita instalar librerías.
Genera un Excel `.xlsx` con una hoja para Cocina, otra para Barra y otra para
Garzones. Incluye nombres, fechas, turnos, días libres y leyenda de horarios.

## Uso

1. Edita `configuracion.json` con los nombres y turnos de tu empresa.
2. En Windows, haz doble clic en `generar.bat`: genera cuatro semanas desde hoy.
3. Abre el archivo en la carpeta `salidas` con Excel o LibreOffice.
4. Revisa la vista previa de impresión y selecciona todo el libro para imprimir las tres áreas.

También puedes elegir fecha, duración y archivo desde una terminal:

```powershell
python horarios.py --inicio 2026-09-28 --semanas 4 --salida salidas/octubre.xlsx
```

Si el archivo ya existe, el programa pide usar otro nombre para proteger cambios manuales.

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

El formato usa papel A4 horizontal, colores suaves y saltos de página entre
semanas. Con equipos grandes una semana puede ocupar más de una página;
ajusta la escala en Excel según tu impresora.

## Verificación

```powershell
python -m unittest discover -s tests -v
```
