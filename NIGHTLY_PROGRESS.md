# Progreso de sesión nocturna

## Estado inicial

- Rama creada: `nightly/v2-polish`.
- `TRADING_ENABLED=false` confirmado en `.env`; no se ejecutarán operaciones financieras reales.
- El árbol de trabajo ya contenía cambios sin commitear antes de esta sesión. Se conservaron sin resetear ni sobrescribir; incluyen una migración modular reciente y código de autenticación multiusuario que contradice `PROJECT_BRIEF.md`, `ARCHITECTURE.md` y `VERSIONS.md`.
- Decisión inicial: tratar el soporte multiusuario como deuda/deriva de alcance y no ampliarlo. Se mantendrá la instancia de usuario único como comportamiento soportado y se documentará cualquier código legado que quede fuera del flujo.

## Baseline

- Tests: **bloqueados durante la colección** por `SyntaxError` en `app/modules/dca/callbacks.py:85` (falta una coma después de una asignación dentro de `edit_message_text`). No se pudo obtener número de tests ejecutados.
- Ruff: **falló** por los dos errores de sintaxis en `app/modules/dca/callbacks.py` (líneas 85 y 110).
- Type checker: **falló** durante el análisis por el mismo error de sintaxis; el entorno tiene `mypy` disponible.
- Coverage: no hay configuración/ejecutable utilizable detectado en el baseline.
- El baseline se ejecutó con Python 3.14 del entorno.

## Tareas realizadas

- Corregido un `SyntaxError` en callbacks DCA que impedía importar la aplicación.
- Añadida migración SQLite aditiva para `dca_rules.asset_name`, conservando bases V1 existentes.
- Endurecido `OrderService`: respuestas inciertas de Wallbit pasan a `verification_required` sin retry ciego.
- Añadido test de 100 confirmaciones concurrentes: una ejecución lógica y 99 rechazos.
- Endurecido `WallbitClient`: `AsyncClient` compartido, caché corta/coalescing de activos, network errors,
  JSON malformado y respuestas inesperadas con excepciones de dominio.
- Añadida capa `app/shared/presentation/` con formato común, loading temprano, edición del mensaje y errores UX.
- `/saldo`, `/inv` y `/reporte` muestran feedback temprano y editan el mismo mensaje cuando Telegram lo permite.
- Añadido `modules/advisor/` opcional y de solo lectura con provider intercambiable, `ToolRegistry` tipado,
  `MockProvider` y adapter Wallsync sin endpoint inventado. Incluido `/analizar`.
- Añadidos `AI_ENABLED`, `AI_PROVIDER`, `WALLSYNC_ENABLED`, `FX_CACHE_TTL_SECONDS` y
  `WALLBIT_CACHE_TTL_SECONDS`.
- Configuración y README alineados con una sola instancia/usuario; `MULTI_USER_ENABLED=true` se rechaza
  en configuración de producción y no se anuncia como feature.
- Añadidos `python -m app doctor`, Docker, `.dockerignore`, CI y `DEPLOYMENT.md`.
- Actualizada configuración visible para mostrar Trading real e IA.

### Wallsync

Se investigaron fuentes públicas. `wallsync.cc` describe agentes financieros y señala que su infraestructura
usa Wallbit, pero no publica una API, MCP, flujo de autenticación o documentación de integración para terceros.
Por seguridad, se dejó `WallsyncProvider` preparado y `WALLSYNC_ENABLED=false`; no se scrapea ni automatiza
la web.

## Commits

- `cec2315` fix: repair DCA callback formatting syntax
- `35ec7db` fix: migrate legacy DCA metadata safely
- `f8df23c` security: require verification after uncertain trade response
- `0f17606` fix: harden Wallbit response and network handling
- `1db9292` feat: unify Telegram loading and error presentation
- `70d2593` perf: coalesce short-lived Wallbit asset reads
- `b180132` feat: add optional read-only advisor module
- `ff13287` docs: align single-user configuration and advisor setup
- `63f5720` chore: add doctor Docker CI and deployment guidance
- `6515a9d` test: cover concurrent pending order confirmation
- `e9a8778` security: reject unsupported multi-user runtime mode

## Problemas y decisiones

- No se leerán ni imprimirán secretos del `.env`.
- No se harán requests de escritura contra Wallbit.
- El README actual anuncia un modo multiusuario y login, en contradicción con las fuentes de verdad; requiere corrección documental y revisión del código de alcance.

## TODOs

- Corregir primero el error sintáctico y repetir baseline.
- Auditar autorización de comandos y callbacks.
- Revisar `OrderService` para idempotencia, expiración y timeout financiero.
- Revisar cliente HTTP, concurrencia/cache y errores de dominio.
- Mejorar presentación Telegram y tests críticos.
- Preparar Advisor opcional sin capacidad de trading.
- Actualizar documentación, Docker/CI y revisiones finales.
