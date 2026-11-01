# BIM Studio 360 — Auditoría inicial RevitMCP y hoja de ruta Revit 2027

**Estado:** diagnóstico estático inicial de repositorios; NO equivale a certificación ni prueba en Revit 2027.  
**Fecha:** 2026-10-31  
**Repositorio de trabajo:** `bimgdl1-max/BIMStudio360-RevitMCP`  
**Rama de aislamiento:** `bimstudio360/auditoria-y-base-2027`  
**Origen y licencia:** `oakplank/RevitMCP`, MIT. Mantener `LICENSE.md` y los créditos.

## Hallazgos comprobados

- El código vigente del fork define **49 herramientas** en **9 módulos**, según llamadas a `ToolDefinition` y sus constantes. La descripción del README todavía indica **46**. El inventario se fija en `tool-baseline.json` y se controla con `scripts/bimstudio360_inventory.py --check`.
- El servidor usa `FastMCP` en transporte `stdio` y dispone de superficie web Flask; `bootstrap.py` registra las herramientas desde `tools/registry.py`.
- El modelo en ejecución se comunica mediante pyRevit Routes (espacio `revit-mcp-v1`), con llamadas HTTP locales configuradas en `core/revit_client.py`. La implementación expone herramientas de consulta y escritura (parámetros, borrado, etiquetado, vistas y tablas).
- El módulo de borrado implementa `dry_run`, confirmación explícita y límite `max_count`, según `element_operation_tools.py` y `element_operation_routes.py`.
- El proyecto incluye pruebas Python (`lib/RevitMCP_ExternalServer/tests/test_external_server.py`). No se han ejecutado contra Revit 2027 durante esta auditoría.
- En los archivos inspeccionados (`core/revit_client.py`, `bootstrap.py`, algunos handlers en `lib/routes`) **no quedó verificado un mecanismo general de autorización por petición en el puente HTTP**. Esto es una pregunta de seguridad pendiente, no una afirmación de vulnerabilidad explotable. La URL del puente utiliza `localhost`; la superficie web toma `FLASK_HOST` de configuración y debe mantenerse en loopback.
- El repositorio paralelo `bimgdl1-max/mcp-server-for-revit-python` es un fork distinto de `mcp-servers-for-revit/mcp-server-for-revit-python`: su `mcp-tool-manifest.json` declara **20 herramientas**, y documenta emparejamiento Windows DPAPI y revisión de operaciones. No mezclar sus bases de código directamente sin analizar API, derechos y pruebas.

## Comparación funcional inicial

| Dominio | OakPlank / fork BIM Studio 360 | Fork paralelo Python |
| --- | --- | --- |
| Consulta de modelo, niveles, propiedades | Sí, según registro y README | Sí, según manifiesto |
| Vistas, imágenes y hojas | Sí | Sí |
| Filtrado, selección y sincronización de parámetros | Sí | Parcial: depende del conjunto de 20 herramientas |
| Tablas de planificación (schedules) | Sí, 10 herramientas | No figuran en el manifiesto consultado |
| Etiquetas de elementos/rooms | Sí, 3 herramientas | No figuran en el manifiesto consultado |
| Seguridad de emparejamiento Windows | Pendiente de comprobar/homologar | Documentada en `SECURITY.md` |
| Apertura, guardado y sincronización central | No aparecen como herramientas MCP nominales en el registro auditado | Sí, figuran en manifiesto |
| Ejecución arbitraria de código IronPython | No figura como herramienta nominal en el registro auditado | Sí, con revisión humana documentada; riesgo alto |

**Precaución:** "no figura" no demuestra imposibilidad técnica ni ausencia en componentes adicionales. Esta tabla compara inventarios, no pruebas funcionales.

## Matriz de validación antes de trabajar con proyectos reales

| Puerta de control | Prueba requerida | Estado |
| --- | --- | --- |
| 1. Integridad de catálogo | `python scripts/bimstudio360_inventory.py --check` | Implementado para CI; revisar resultado del workflow |
| 2. Pruebas unitarias externas | Ejecutar `pytest` en entorno con requisitos fijados | Pendiente |
| 3. pyRevit/Revit 2027 | Abrir modelo de prueba y verificar rutas, conexión, puerto y sesión | Pendiente |
| 4. Lectura BIM | Niveles, categorías, selección, familias, parámetros, vistas, schedules | Pendiente |
| 5. Escritura segura | Preview, aprobación humana y `Transaction`; prueba de rollback con modelo desechable | Pendiente |
| 6. Seguridad del puente | Autenticación local, origen/host, permisos, exposición LAN, secretos, timeout/reintentos | Pendiente |
| 7. Worksharing | Pruebas de edición/guardado/sincronización con central en entorno controlado | Pendiente |
| 8. Instalación independiente | Otra carpeta pyRevit y otro cliente MCP sin reemplazar instalación actual | Pendiente |

## Plan de evolución

**Etapa A — Catálogo y control de cambios (esta entrega):** rama aislada, baseline de 49 herramientas, prueba de consistencia sin iniciar Revit y auditoría documental.

**Etapa B — Seguridad:** auditoría del puente HTTP; defensa loopback; evaluar emparejamiento y autorización por herramienta; límites por operación; evitar reintentos automáticos en operaciones con efectos secundarios.

**Etapa C — Revit 2027:** verificar API real en Windows, `ElementId.Value`, categorías, transacciones, cambios de unidad y pyRevit. No declarar compatibilidad antes de pasar la matriz.

**Etapa D — Modelado BIM ampliado:** diseñar herramientas con especificación estricta, vista previa, transacciones y pruebas: muros → suelos → columnas/vigas → puertas/ventanas → habitaciones/áreas → listas y hojas. Cualquier cambio de geometría requiere confirmación antes de ejecutarse.

**Etapa E — Otros conectores:** AutoCAD y Blender con repositorios independientes, compartiendo contratos MCP, pruebas y seguridad, no copiando rutas específicas de Revit.

## Comandos de verificación

Desde la raíz del repositorio:

```powershell
python scripts/bimstudio360_inventory.py --check
python scripts/bimstudio360_inventory.py --markdown
python -m unittest discover -s scripts/tests -p "test_*.py" -v
```

Para cambios **intencionales** en la lista de herramientas: ejecutar `--write` en una rama, revisar el diff y solicitar revisión. **No actualizar el baseline para silenciar una eliminación inesperada.**

## Reglas de preservación

- No modificar el `main` original, la instalación `RevitMCP.extension` de Windows, las credenciales ni proyectos RVT.
- Mantener el archivo de licencia y el crédito al autor del software upstream.
- No incorporar ejecución arbitraria de scripts, borrados masivos o guardado central sin controles, revisión y modelos de prueba.
- La rama de auditoría no ejecuta herramientas en un modelo real.
