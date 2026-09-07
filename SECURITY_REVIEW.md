# Revisión de seguridad

Fecha: sesión `nightly/v2-polish`

## CRITICAL

- **Ninguno identificado en el código revisado.** No se ejecutaron operaciones de escritura contra Wallbit.

## HIGH

- **Orden con resultado incierto:** corregido. Un timeout, error de red o 5xx no marca la orden como
  fallida ni la reintenta; pasa a `verification_required` y se informa al usuario que no debe reintentar.
- **Doble confirmación:** corregido y cubierto con 100 confirmaciones concurrentes. La reclamación se
  hace mediante `UPDATE` condicional en SQLite, no con una variable Python.
- **Trading accidental:** `TRADING_ENABLED=false` permanece en `.env`; los tests usan cliente mock y
  no dinero real. El advisor no registra ni conoce `execute_trade`.
- **Modo multiusuario heredado:** la configuración de producción rechaza `MULTI_USER_ENABLED=true` y
  el README/.env.example ya no lo presentan. El módulo legado y sus tests permanecen para no borrar
  trabajo previo, pero no forman parte del flujo soportado.

## MEDIUM

- **Callback de órdenes:** usa un ID local no secreto. El ID se vuelve a validar contra usuario,
  propiedad, estado, expiración y regla DCA antes de cualquier cambio; callback data nunca es fuente
  de verdad.
- **Credenciales:** se cargan desde `.env`; el logger sanitiza token de Telegram, API key, Bearer y
  credenciales de contexto. No se imprimen secretos en doctor, tests ni documentación.
- **Logs:** se registran IDs técnicos, símbolos y duraciones, nunca headers Authorization ni API keys.
  Debe revisarse cualquier nuevo logger antes de añadir datos financieros detallados.
- **Dependencias:** CI ejecuta Ruff, pytest y mypy sobre los módulos tipados modificados. Falta añadir
  un escaneo SCA/Dependabot si el repositorio lo adopta más adelante.
- **SQLite:** la migración actual es aditiva y conserva datos; los backups deben protegerse con permisos
  de filesystem y fuera del repositorio.

## LOW

- **Enumeración de IDs locales:** los IDs de callbacks no contienen importes ni secretos, pero son
  predecibles. La autorización y las transiciones atómicas impiden usarlos para leer u operar órdenes
  ajenas.
- **Provider Wallsync:** permanece desactivado porque no se encontró API/MCP público oficial verificable.
  No se automatiza su web ni se inventa autenticación.

## Validaciones realizadas

- `TRADING_ENABLED=false` confirmado en el `.env` de la instancia.
- `pytest`: 101 tests pasan después de añadir el test de concurrencia.
- `ruff check .`: pasa.
- `mypy --follow-imports=skip` sobre módulos nuevos y endurecidos: pasa.
- No se hicieron requests de escritura, compras ni ventas.
