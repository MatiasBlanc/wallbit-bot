# Informe de sesión nocturna — Wallbit Assistant Bot

## 1. Resumen ejecutivo

Se dejó una V1 más segura y pulida sin reconstruir el proyecto ni introducir SaaS/multiusuario. La rama
`nightly/v2-polish` contiene hardening de órdenes, UX de Telegram, caché/coalescing HTTP, Advisor opcional,
Docker, CI, doctor y documentación.

`TRADING_ENABLED=false` se mantuvo durante toda la sesión. No se hicieron compras, ventas ni requests de
escritura contra Wallbit.

## 2. Funcionalidades implementadas

- Migración SQLite aditiva para instalaciones V1 con reglas DCA antiguas.
- Estado `verification_required` para respuestas financieras inciertas.
- Confirmación idempotente mediante actualización SQL condicional.
- Caché corta y request coalescing para activos Wallbit.
- Excepciones de dominio para respuestas inesperadas y JSON malformado.
- Presentación común y loading temprano en `/saldo`, `/inv` y `/reporte`.
- `python -m app doctor`.
- Dockerfile no root, volumen SQLite y `.dockerignore`.
- GitHub Actions con Ruff, pytest y mypy acotado a módulos tipados.

## 3. Mejoras UX

- El feedback inicial se edita en lugar de acumular mensajes cuando Telegram lo permite.
- Errores de rate limit, autenticación y disponibilidad tienen mensajes accionables en español.
- Se añadió `app/shared/presentation/` con formatters y estados comunes.
- `/config` muestra moneda, reporte, alertas, trading real e IA.
- Menú principal incorpora `🤖 Analizar` sin eliminar comandos.
- `/analizar` ofrece resumen, riesgo, concentración y rendimiento.

## 4. Mejoras de performance

- `WallbitClient` reutiliza un `httpx.AsyncClient` con pool y límites.
- Lecturas repetidas de activos se coalescen y se cachean por un TTL corto configurable.
- `/reporte` conserva las lecturas concurrentes independientes mediante `asyncio.gather`.
- Variables nuevas: `WALLBIT_CACHE_TTL_SECONDS` y `FX_CACHE_TTL_SECONDS`.
- Benchmark local con mocks, 5 posiciones, 5 transacciones por posición, 1 ms de latencia y una corrida:
  - balance: 14.85 ms, 8 requests HTTP, máximo 4 concurrentes;
  - portfolio: 9.60 ms, 1 request HTTP;
  - reporte: 7.11 ms, 3 requests HTTP, máximo 2 concurrentes;
  - DCA batched: 72.45 ms, 2 requests HTTP frente a 20 del escenario no agrupado.
- No existe benchmark numérico pre-optimización, por lo que no se afirma un porcentaje de mejora.

## 5. Mejoras de seguridad

- Timeout/5xx durante una orden ya no se convierte en fallo reintentable: queda en
  `verification_required`.
- 100 confirmaciones simultáneas producen una única ejecución lógica y 99 rechazos.
- No hay retry automático de trades.
- `TRADING_ENABLED=false` continúa siendo el modo seguro.
- `execute_trade` no existe en el registro de herramientas IA.
- `MULTI_USER_ENABLED=true` se rechaza en configuración de producción; el soporte heredado no se anuncia
  ni se registra en el flujo normal.
- Logs y excepciones HTTP no incluyen cuerpos crudos innecesarios ni credenciales.

## 6. IA implementada

Se añadió `app/modules/advisor/` con:

- `AdvisorService`;
- contrato `AIProvider`;
- `MockProvider`;
- `WallsyncProvider` preparado;
- `AdvisorContext` compacto;
- `ToolRegistry` con validación Pydantic;
- tools de balance, portfolio, posición, movimientos, DCA, alertas, FX y reporte.

La IA solo consulta servicios de dominio. No recibe acceso directo a `WallbitClient` y no puede ejecutar
trading ni crear mutaciones automáticamente.

## 7. Estado Wallsync

Se revisaron fuentes públicas. `wallsync.cc` presenta agentes financieros y declara infraestructura
potenciada por Wallbit, pero no publica un API, MCP, autenticación o capabilities para integración de
terceros verificables. Por eso no se inventó un endpoint ni se scrapeó la web.

Estado: adapter preparado, `WALLSYNC_ENABLED=false`.

## 8. Tests agregados o actualizados

- Migración/compatibilidad de schema SQLite.
- JSON malformado del cliente Wallbit.
- Caché y coalescing concurrente de activos.
- Timeout/resultado incierto de trade.
- 100 confirmaciones concurrentes sobre una PendingOrder.
- Advisor desactivado, herramientas tipadas y rechazo de `execute_trade`.

## 9. Cobertura y validaciones

- Baseline inicial: colección bloqueada por un `SyntaxError` en DCA; después de corregirlo hubo 93 tests
  pasando y 1 fallo de migración heredada.
- Estado final: **102 passed**.
- `ruff check .`: **OK**.
- Mypy dirigido a los módulos nuevos/endurecidos con `--follow-imports=skip`: **OK**.
- Mypy completo del repositorio en baseline: falló con 386 errores heredados de tipado SQLAlchemy/Telegram;
  no se ocultaron ni se reescribió masivamente el código para silenciarlos.
- `compileall`: **OK**.
- Coverage: no hay comando/configuración de coverage disponible en el entorno.
- Docker build: no ejecutado; Docker no está instalado en el entorno actual.

## 10. Commits realizados

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
- `3894cc8` docs: record nightly progress and security review
- `35d27c4` fix: classify HTTP timeouts as unavailable

El árbol conserva además cambios preexistentes del usuario que ya estaban sin commitear al comenzar; no se
resetearon ni borraron.

## 11. Bugs encontrados

- Error de sintaxis en dos callbacks DCA.
- Bases SQLite existentes no tenían `asset_name`, provocando `OperationalError` en relaciones DCA.
- Respuesta JSON malformada no se transformaba a excepción de dominio.
- Errores de red y resultado financiero incierto no diferenciaban un fallo confirmado de un estado que
  requería verificación.
- README y `.env.example` anunciaban multiusuario aunque las fuentes de verdad lo excluyen.

## 12. Bugs corregidos

Todos los puntos anteriores fueron corregidos o acotados, con tests para sintaxis/migración, cliente,
orden incierta y alcance single-user.

## 13. Issues pendientes

- El tipado completo del código heredado sigue reportando 386 diagnósticos mypy.
- Docker no pudo validarse construyendo imagen por ausencia del binario Docker.
- No se agregó provider real de IA: no había endpoint/configuración oficial disponible en el proyecto.
- El adapter Wallsync requiere documentación oficial de API/MCP antes de implementarse.
- Falta un sistema de métricas persistentes; actualmente se registran eventos y las mediciones del
  benchmark son locales.

## 14. Archivos importantes modificados

- `app/modules/orders/service.py`
- `app/modules/orders/repository.py`
- `app/infrastructure/wallbit/client.py`
- `app/infrastructure/database/database.py`
- `app/shared/presentation/`
- `app/modules/advisor/`
- `app/__main__.py`
- `Dockerfile`, `.dockerignore`, `.github/workflows/ci.yml`
- `DEPLOYMENT.md`, `SECURITY_REVIEW.md`, `README.md`, `.env.example`

## 15. Nuevas variables `.env`

```env
WALLBIT_CACHE_TTL_SECONDS=5
FX_CACHE_TTL_SECONDS=300
AI_ENABLED=false
AI_PROVIDER=mock
WALLSYNC_ENABLED=false
```

## 16. Instrucciones para probar mañana

```bash
git switch nightly/v2-polish
pip install -r requirements-dev.txt
pytest -q
ruff check .
python -m app --help
# Con un .env válido y solo lectura de Wallbit:
python -m app doctor
```

Mantén `TRADING_ENABLED=false`. Para probar Telegram, usa primero `/start`, `/saldo`, `/inv`,
`/reporte`, `/config`, `/dca` y `/alerta` con credenciales de lectura y mocks cuando corresponda.

## 17. Instrucciones para activar IA

En `.env`:

```env
AI_ENABLED=true
AI_PROVIDER=mock
WALLSYNC_ENABLED=false
```

Reinicia el bot y usa `/analizar`. El provider `mock` valida el circuito y las herramientas, pero no es
un modelo generativo. No actives Wallsync hasta contar con integración oficial verificable.

## 18. Instrucciones para deploy

Seguir `DEPLOYMENT.md`: VM Linux Azure pequeña, Docker, volumen persistente `/data`, `.env` con permisos
600, `--restart unless-stopped`, backups SQLite y logs sin secretos.

## 19. Riesgos conocidos

- Cualquier activación futura de trading real debe probarse con permisos mínimos y un procedimiento de
  reconciliación externo; un timeout puede requerir verificación manual en Wallbit.
- SQLite requiere una sola réplica y backups consistentes.
- El módulo de autenticación heredado permanece en el árbol para no borrar trabajo previo, aunque el
  arranque productivo rechaza el modo multiusuario.

## 20. Próximos pasos recomendados

1. Añadir un provider IA real solo tras fijar endpoint, permisos y secreto en documentación oficial.
2. Añadir migraciones versionadas si aparecen más cambios de schema.
3. Reducir progresivamente los diagnósticos mypy heredados por módulo.
4. Añadir Dependabot/SCA y un job de cobertura cuando se defina el umbral.
5. Ejecutar `docker build` y una prueba de restauración SQLite en CI o una VM de staging.
