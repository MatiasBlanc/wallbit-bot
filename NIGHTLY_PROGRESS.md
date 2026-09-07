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

_(Se actualizará después de cada cambio lógico.)_

## Commits

_(Se añadirá el hash y el propósito de cada commit.)_

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
