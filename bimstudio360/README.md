# BIM Studio 360 — API local + panel de Revit, prototipo 0.1

## Estado y alcance

Implementación inicial sobre `main` 32c9ae80f691dffca644ebc70217ec70f8cdf0fc.
**Distribución aditiva:** todos los archivos nuevos están bajo `bimstudio360/`.
Ningún archivo original del MCP se modifica, mueve ni elimina.
La extensión de interfaz se instala por separado como `BIMStudio360.extension`.

El registro contiene **49 funciones**; el README anterior indicaba 46 porque omitía
las tres herramientas de etiquetado. La API y el panel leen el registro existente.
Se mantienen autoría y licencia MIT originales.

Incluye:
- API HTTP local independiente en `127.0.0.1:8765`, con token Bearer.
- Catálogo de 49 herramientas, esquemas de entrada y OpenAPI 3.1.
- Ejecución directa mediante el mismo `ToolRegistry.dispatch`.
- Pestaña **BIM Studio 360**, panel **Automatizacion**, botón **Herramientas**.
- Ventana nativa flotante WPF: catálogo, descripción, esquema, parámetros JSON y resultado.
- Confirmación adicional para operaciones fuera de la lista explícita de consultas.
  Los argumentos `dry_run`, `confirm` u otros del propio comando siguen siendo necesarios
  cuando lo requiera su contrato. La confirmación del sobre HTTP no los sustituye.
- Solicitudes de la ventana en un hilo de fondo para mantener libre la interfaz de Revit.

No es todavía un instalador firmado ni un panel acoplable. Los formularios por tarea
se desarrollarán después de validar la base. No incorpora nuevas funciones de modelado.

## Instalación de ensayo en Windows

1. Descargar la rama `bimstudio360/api-panel-isolated-v1` en una carpeta de trabajo.
   Mantener la instalación original `RevitMCP.extension` como está. Copiar únicamente
   `bimstudio360/BIMStudio360.extension` a una raíz de extensiones pyRevit, junto a la
   extensión original. Esta extensión nueva sólo añade la interfaz; no registra rutas
   ni sustituye el puente original. No instalar otra copia de RevitMCP.
2. Usar un entorno CPython 3.11 o 3.12 para el servidor; instalar dependencias desde
   la raíz de la copia descargada del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r bimstudio360\requirements.txt
```

3. Abrir Revit, habilitar pyRevit Routes según el README y abrir una **copia de ensayo**
   del proyecto. Recargar pyRevit para que aparezca la pestaña BIM Studio 360.
4. En PowerShell, desde la raíz de la copia descargada, generar un token de sesión y ejecutar:

```powershell
$env:BIMSTUDIO360_API_TOKEN = (& .\.venv\Scripts\python.exe -c 'import secrets; print(secrets.token_urlsafe(32))')
$env:BIMSTUDIO360_API_TOKEN | Set-Clipboard
.\.venv\Scripts\python.exe bimstudio360\api_server.py
```

5. En Revit, abrir **BIM Studio 360 → Automatizacion → Herramientas**. Pegar el token
   en el campo protegido y pulsar **Conectar**. El catálogo debe mostrar 49 funciones.
   El token no se guarda en el panel. Borrar el portapapeles después de pegarlo.
6. Elegir `get_revit_project_info`, dejar `{}` y pulsar **Ejecutar función**.
   Comparar el documento devuelto con la copia abierta antes de ejecutar cambios.

El servidor debe permanecer abierto. Esta API no necesita una clave de proveedor IA
para ejecutar directamente herramientas. Conserva las dependencias del MCP actual.

## API

Todas las rutas exigen `Authorization: Bearer <token>` y acceso desde loopback.
No se habilita CORS ni se montan las rutas antiguas de chat en este servidor.

| Método | Ruta | Resultado |
|---|---|---|
| GET | `/api/v1/health` | Disponibilidad del servidor y conteo; no certifica conexión con Revit |
| GET | `/api/v1/tools` | Catálogo, esquemas y requisito de confirmación |
| GET | `/api/v1/openapi.json` | Contrato generado para las 49 operaciones |
| POST | `/api/v1/tools/{name}/execute` | Ejecución de una herramienta |

Ejemplo Python, con la misma variable de entorno configurada en ese proceso:

```python
import os
import requests

response = requests.post(
    'http://127.0.0.1:8765/api/v1/tools/get_revit_project_info/execute',
    headers={'Authorization': 'Bearer ' + os.environ['BIMSTUDIO360_API_TOKEN']},
    json={'arguments': {}},
    timeout=90,
)
response.raise_for_status()
print(response.json())
```

Los cambios requieren `"confirm": true` en el sobre y los parámetros propios de la
herramienta en `arguments`. No usar confirmaciones globales automáticas para un agente.
Las rutas documentadas antes como `/project`, `/schedules`, etc. eran ejemplos: esta
primera implementación usa el nombre exacto de cada herramienta para conservar paridad.

Códigos: 400 datos inválidos; 401 token incorrecto; 403 acceso no local o falta de
confirmación; 404 herramienta desconocida; 409 operación en curso; 422 error reportado
por la herramienta. Las peticiones excesivamente grandes reciben 413.
Las operaciones se serializan en este proceso, sin reintentos automáticos del adaptador.

## Pruebas y límites de validación

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s bimstudio360\tests -p 'test_*.py' -v
.\.venv\Scripts\python.exe -m unittest discover -s lib\RevitMCP_ExternalServer\tests -p 'test_*.py' -v
```

Las pruebas HTTP usan el catálogo real y simulan la ejecución sobre Revit. Verifican
contratos, autenticación, confirmaciones, exclusión de operaciones concurrentes y errores.
Resultado en este entorno: 12 pruebas nuevas y 67 existentes aprobadas, más arranque HTTP real
con autenticación y catálogo de 49 funciones. Sintaxis Python y XML del panel verificadas.
No acreditan resultados geométricos ni compatibilidad real con Revit 2027.

Pendiente de aceptación en Windows/Revit:
- Carga de la pestaña, apertura/cierre/reapertura de la ventana y conexión con token.
- Consulta de proyecto, selección, vistas y tablas.
- Escrituras y eliminaciones con simulación previa donde exista; comprobar resultados
  y deshacer en el modelo de ensayo.
- Etiquetado de elementos y habitaciones y exportación de imágenes.
- Comprobar las 49 herramientas con casos representativos y registrar incidencias.

El puente original sigue dependiendo del documento activo y de la detección de puerto.
Para este prototipo utilizar una sola sesión Revit y no cambiar de documento durante
una operación. No ejecutar MCP, chat y API simultáneamente sobre el mismo modelo: el
bloqueo añadido sólo coordina llamadas de este proceso API. El siguiente hito de
producción debe fijar sesión/documento y coordinar todos los canales dentro del puente.

Los puertos internos originales de pyRevit no quedan autenticados por añadir esta
capa. Mantenerlos locales; endurecer el puente es un requisito antes de acceso remoto.
El servidor Flask incluido es de desarrollo. No publicar este prototipo en Internet.
Un timeout no garantiza cancelación: comprobar el estado de Revit antes de repetir
una escritura. Los flujos heredan el comportamiento de transacciones del MCP y no
prometen atomicidad total ni rollback de archivos o memoria.

## Siguiente entrega

Tras validar la conexión real: formularios en español para las operaciones frecuentes,
selección inequívoca de sesión/documento, control común de ejecución y empaquetado.
La migración a un complemento C# independiente de pyRevit requiere un proyecto adicional.
