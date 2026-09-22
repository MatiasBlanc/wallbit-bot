# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/),
y este proyecto adhiere a [Versionado Semántico](https://semver.org/lang/es/).

## [Unreleased]

### Seguridad y fiabilidad

- Las interacciones del bot ahora solo se aceptan en chats privados.
- Alertas y propuestas DCA usan un outbox SQLite persistente con reintentos tras fallos de Telegram.
- `/ordenes` incluye compras aún pendientes de confirmación.
- SQLite activa claves foráneas, WAL y espera ante bloqueos, y registra migraciones aditivas en `schema_migrations`.
- Se añadió verificación `integrity_check` para respaldos mediante `python -m app verify-backup --file RUTA`.
- CI incorpora cobertura mínima de código de producción, auditoría SCA, mypy completo sin diagnósticos y una prueba de integración Wallbit opt-in solo de lectura.
- Los modelos ORM se migraron a la sintaxis tipada de SQLAlchemy 2 (`Mapped` y `mapped_column`).

## [1.0.0] - 2026-09-06

### Agregado

- **Bot de Telegram** con 8 comandos: `/start`, `/saldo`, `/inv`, `/dca`, `/alerta`, `/historial`, `/reporte`, `/config`
- **Integración con API de Wallbit**: consulta de saldos, portafolio, cotizaciones, historial de transacciones y ejecución de trades
- **Sistema DCA (Dollar Cost Averaging)**: creación, listado, pausa/activación y eliminación de reglas de compra recurrente
- **Sistema de alertas de precio**: creación de alertas por precio objetivo (superior/inferior) con notificaciones automáticas
- **Reportes diarios automáticos**: resumen programado con saldo, portafolio y rendimiento
- **Historial de transacciones**: consulta paginada del historial de movimientos
- **Sistema de órdenes pendientes**: confirmación manual antes de ejecutar compras, con expiración automática
- **Modo simulación**: operación sin ejecutar trades reales (`TRADING_ENABLED=false`)
- **Seguridad**: restricción por `TELEGRAM_ALLOWED_USER_ID`, sanitización de secretos en logs
- **Persistencia local**: SQLite para reglas DCA, alertas, órdenes pendientes y configuración del usuario
- **Tareas programadas**: APScheduler con jobs para reporte diario, verificación DCA, verificación de alertas y expiración de órdenes
- **Suite de tests**: 39 tests unitarios cubriendo todos los servicios y utilidades
- **Documentación completa** en español

[Unreleased]: https://github.com/mblanc/wallbit-bot/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/mblanc/wallbit-bot/releases/tag/v1.0.0
