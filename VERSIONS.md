# Wallbit Assistant Bot — Versions

## Dirección

Wallbit Assistant Bot es y seguirá siendo un **repositorio open source self-hosted para una sola persona por instancia**.

No existe roadmap multiusuario.

No existe objetivo SaaS.

Cada usuario clona y ejecuta su propia copia.

Roadmap:

```text
V1
Personal Automation Bot
        ↓
V1.1
Hardening + Deploy
        ↓
V2
AI + Wallsync
        ↓
V2.1
Smart Automations
        ↓
V3
Self-Hosting Experience
        ↓
V3.x
Integrations + Polish
```

---

# V1 — Personal Automation Bot

## Estado

**Implementada / estable**

## Objetivo

Automatización personal de Wallbit desde Telegram.

## Funcionalidades

### `/saldo`

- saldo;
- conversiones;
- patrimonio cuando esté disponible.

### `/inv`

- portfolio;
- P&L;
- rentabilidad.

### `/inv TICKER`

Detalle de posición.

### `/dca`

- crear;
- pausar;
- reactivar;
- eliminar;
- scheduler;
- confirmación.

### `/alerta`

- activos;
- FX.

### `/historial`

Movimientos recientes.

### `/reporte`

Resumen financiero.

### Reporte diario

Automático.

### `/config`

Configuración local.

## Seguridad

- TELEGRAM_ALLOWED_USER_ID;
- TRADING_ENABLED=false;
- dry-run;
- PendingOrder;
- expiración;
- idempotencia;
- sanitización de logs.

---

# V1.1 — Production Hardening

## Objetivo

Dejar la V1 preparada para ejecutarse 24/7.

## Tests

Aumentar cobertura en:

- OrderService;
- DCA;
- Alerts;
- Scheduler;
- WallbitClient;
- errores HTTP;
- idempotencia.

## Concurrencia

Simular confirmaciones simultáneas sobre una misma orden.

Resultado esperado:

```text
1 ejecución
N-1 rechazos
```

## CI

GitHub Actions:

```text
pytest
ruff
type checking
```

## Docker

Agregar:

```text
Dockerfile
.dockerignore
```

## Health checks

Opcional:

```text
GET /health
GET /ready
```

## Deployment

Documentar:

- Azure;
- Docker;
- VM Linux;
- systemd;
- backups;
- secrets.

## Observabilidad

- logging estructurado;
- sanitización;
- request IDs;
- métricas simples.

---

# V2 — AI + Wallsync

## Objetivo

Agregar análisis inteligente sin tocar el flujo seguro de trading.

## Advisor

Nuevo módulo:

```text
modules/advisor/
```

## Casos de uso

```text
¿Cómo van mis inversiones?

¿Qué cambió esta semana?

¿Estoy demasiado concentrado en tecnología?

¿Qué riesgo tiene mi cartera?

Explícame mi rendimiento.
```

## Wallsync

Investigar la integración oficial disponible.

No inventar API, MCP, OAuth ni capacidades.

Mantener abstracción:

```text
AdvisorProvider
```

Feature flags:

```env
AI_ENABLED=false
WALLSYNC_ENABLED=false
```

## Seguridad

IA:

- lee;
- analiza;
- explica;
- sugiere.

IA no:

- compra;
- vende;
- confirma;
- ejecuta DCA;
- llama directamente a OrderService para operar.

Flujo:

```text
Advisor
   ↓
Análisis
   ↓
Usuario decide
   ↓
PendingOrder
   ↓
Confirmación
   ↓
OrderService
```

## UX

Agregar:

```text
/advisor
```

o:

```text
/analizar
```

Texto libre opcional cuando AI_ENABLED=true.

---

# V2.1 — Smart Automations

## Objetivo

Permitir reglas expresadas en lenguaje natural, pero ejecutadas por código determinístico.

Ejemplos:

```text
Avísame si VOO baja de 450.

Cada domingo envíame un resumen semanal.

Si USD/CLP supera 980, notifícame.

Recuérdame mi DCA los lunes.
```

Flujo:

```text
Lenguaje natural
   ↓
AI parser
   ↓
Regla estructurada
   ↓
Validación
   ↓
Scheduler
```

La IA nunca ejecuta por sí sola.

---

# V3 — Self-Hosting Experience

## Objetivo

Hacer la instalación y mantenimiento extremadamente simples.

## Setup

Ideal:

```bash
git clone ...
cp .env.example .env
docker compose up -d
```

## Setup wizard

Opcional:

```bash
python setup.py
```

Puede solicitar:

- Telegram Bot Token;
- Telegram User ID;
- Wallbit API Key;
- moneda;
- timezone;
- horario.

El resultado se guarda localmente en `.env`.

## Doctor

Agregar:

```bash
python -m app doctor
```

Debe comprobar:

- configuración;
- Telegram;
- Wallbit;
- DB;
- scheduler;
- permisos.

## Backups

Herramienta para backup local de SQLite.

## Updates

Documentar:

```text
git pull
migrations si aplica
restart
```

---

# V3.1 — Integrations

Integraciones opcionales:

- Wallsync;
- Wallbit MCP;
- proveedores FX;
- exportaciones;
- webhooks;
- dashboards opcionales.

Cada integración debe poder activarse o desactivarse.

---

# V3.2 — UX y Polish

## Objetivo

Mejorar experiencia sin aumentar complejidad estructural.

Posibles mejoras:

- menús inline;
- mensajes más claros;
- resúmenes semanales;
- estados visuales;
- mejores errores;
- onboarding dentro de README;
- demo mode;
- screenshots;
- templates.

---

# Fuera de alcance permanente del repositorio

No implementar:

- multiusuario;
- login;
- registro;
- cuentas internas;
- roles;
- organizaciones;
- API Keys de terceros almacenadas centralmente;
- dashboard SaaS;
- backend compartido;
- facturación;
- suscripciones;
- administración de usuarios;
- aislamiento de tenants.

Si alguna vez se quisiera construir eso, debe plantearse como un producto separado.

---

# Principio de versionado

Antes de agregar una feature:

1. ¿Mejora realmente el bot personal?
2. ¿Mantiene una sola instancia por usuario?
3. ¿Puede implementarse dentro del monolito?
4. ¿Aumenta riesgo financiero?
5. ¿Puede probarse?
6. ¿Puede ser opcional?
7. ¿Añade dependencia innecesaria?

Si rompe la simplicidad self-hosted, se posterga o se descarta.

---

# Concepto central

> **Wallbit Assistant es una capa personal de automatización, monitoreo y análisis sobre Wallbit desde Telegram.**

Su valor está en:

- DCA;
- alertas;
- reportes;
- proactividad;
- confirmaciones;
- automatización;
- análisis IA;
- personalización;
- control local.

Cada usuario conserva sus propias credenciales y su propia instancia.
