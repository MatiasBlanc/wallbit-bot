# Wallbit Assistant Bot — Architecture

## 1. Estilo arquitectónico

Wallbit Assistant Bot utiliza un **monolito modular por dominio**.

El proyecto representa una única instancia para un único usuario.

No existe arquitectura multiusuario.

Flujo general:

```text
Telegram / Scheduler
        ↓
Application Modules
        ↓
Services
        ↓
Repositories / External Clients
        ↓
SQLite / Wallbit / Wallsync
```

## 2. Estructura

```text
wallbit-bot/
├── app/
│   ├── core/
│   │   ├── config.py
│   │   ├── constants.py
│   │   ├── logging.py
│   │   ├── security.py
│   │   └── exceptions.py
│   │
│   ├── infrastructure/
│   │   ├── database/
│   │   │   ├── base.py
│   │   │   └── database.py
│   │   │
│   │   ├── wallbit/
│   │   │   ├── client.py
│   │   │   ├── exceptions.py
│   │   │   └── schemas/
│   │   │       ├── balance.py
│   │   │       ├── portfolio.py
│   │   │       ├── orders.py
│   │   │       └── transactions.py
│   │   │
│   │   ├── wallsync/
│   │   │   ├── provider.py
│   │   │   └── client.py
│   │   │
│   │   └── scheduler/
│   │       └── scheduler.py
│   │
│   ├── modules/
│   │   ├── balance/
│   │   │   ├── service.py
│   │   │   ├── handler.py
│   │   │   └── formatting.py
│   │   │
│   │   ├── portfolio/
│   │   │   ├── service.py
│   │   │   ├── handler.py
│   │   │   └── formatting.py
│   │   │
│   │   ├── dca/
│   │   │   ├── models.py
│   │   │   ├── repository.py
│   │   │   ├── service.py
│   │   │   ├── conversation.py
│   │   │   ├── callbacks.py
│   │   │   ├── keyboards.py
│   │   │   └── jobs.py
│   │   │
│   │   ├── alerts/
│   │   │   ├── models.py
│   │   │   ├── repository.py
│   │   │   ├── service.py
│   │   │   ├── conversation.py
│   │   │   ├── callbacks.py
│   │   │   ├── keyboards.py
│   │   │   └── jobs.py
│   │   │
│   │   ├── orders/
│   │   │   ├── models.py
│   │   │   ├── repository.py
│   │   │   ├── service.py
│   │   │   └── callbacks.py
│   │   │
│   │   ├── history/
│   │   │   ├── models.py
│   │   │   ├── repository.py
│   │   │   ├── service.py
│   │   │   └── handler.py
│   │   │
│   │   ├── reports/
│   │   │   ├── service.py
│   │   │   ├── handler.py
│   │   │   └── jobs.py
│   │   │
│   │   ├── settings/
│   │   │   ├── models.py
│   │   │   ├── repository.py
│   │   │   ├── service.py
│   │   │   ├── conversation.py
│   │   │   └── keyboards.py
│   │   │
│   │   └── advisor/
│   │       ├── service.py
│   │       ├── provider.py
│   │       ├── handler.py
│   │       └── formatting.py
│   │
│   ├── bot/
│   │   ├── application.py
│   │   ├── registry.py
│   │   ├── commands.py
│   │   └── error_handler.py
│   │
│   └── shared/
│       ├── formatting/
│       │   ├── currency.py
│       │   └── percentage.py
│       └── datetime.py
│
├── tests/
│   ├── modules/
│   ├── infrastructure/
│   └── conftest.py
│
├── .env.example
├── pyproject.toml
├── Dockerfile
├── README.md
└── main.py
```

## 3. Core

`app/core/` contiene:

- configuración;
- constantes;
- logging;
- seguridad;
- excepciones globales.

No contiene lógica financiera.

## 4. Infrastructure

### Database

Responsable de:

- SQLAlchemy engine;
- sesiones;
- Base;
- SQLite.

PostgreSQL puede soportarse opcionalmente si simplifica deployment, pero no es requisito del producto.

### Wallbit

`WallbitClient` debe:

- usar httpx async;
- gestionar autenticación;
- manejar timeouts;
- manejar errores;
- manejar rate limits;
- transformar respuestas;
- ser mockeable.

La API key llega desde configuración global de la instancia.

### Wallsync

Integración opcional.

Debe estar detrás de:

```python
class AdvisorProvider:
    async def analyze_portfolio(...):
        ...
```

Wallsync nunca debe ser requisito para iniciar el bot.

### Scheduler

Una única instancia central de APScheduler.

## 5. Módulos por dominio

Cada feature vive en su propio módulo.

Ejemplo:

```text
modules/dca/
```

contiene:

- modelo;
- repositorio;
- service;
- conversation;
- callbacks;
- keyboards;
- jobs.

No repartir una feature por carpetas técnicas globales si no es necesario.

## 6. Balance

```text
/saldo
   ↓
BalanceHandler
   ↓
BalanceService
   ↓
WallbitClient
```

## 7. Portfolio

```text
/inv
   ↓
PortfolioHandler
   ↓
PortfolioService
   ↓
WallbitClient
```

## 8. DCA

DCA nunca ejecuta directamente trades.

```text
DCAService
   ↓
PendingOrder
   ↓
OrderService
```

El scheduler solo genera la intención.

## 9. Orders

`OrderService` es el único punto autorizado a ejecutar una orden.

Debe comprobar:

- TRADING_ENABLED;
- PendingOrder;
- estado;
- expiración;
- saldo;
- ticker;
- monto;
- idempotencia;
- confirmación.

Nunca:

```text
Handler → WallbitClient.create_order()
```

Siempre:

```text
Handler
   ↓
OrderService
   ↓
WallbitClient
```

## 10. Alerts

```text
AlertChecker
   ↓
AlertService
   ↓
Market / FX Provider
```

Persistir el estado de alertas para evitar duplicados.

## 11. Reports

```text
ReportService
├── BalanceService
├── PortfolioService
└── ExchangeService
```

No duplicar lógica.

## 12. Advisor

Módulo opcional.

Responsabilidades:

- análisis;
- explicación;
- IA;
- Wallsync;
- resúmenes.

Permitido:

```text
AdvisorService
├── PortfolioService
├── BalanceService
└── AdvisorProvider
```

Prohibido:

```text
AdvisorService → execute_trade()
```

## 13. Base de datos

La base representa datos locales de una única instancia.

### UserSettings

Aunque el nombre se mantenga por compatibilidad, representa las preferencias del único usuario.

Campos:

- telegram_user_id;
- default_currency;
- timezone;
- report_time;
- alerts_enabled;
- ai_enabled;
- trading_enabled;
- last_daily_report.

No existe tabla `User`.

No existe `user_id` en cada entidad.

No existe ownership multiusuario.

### DCARule

- ticker;
- amount_usd;
- frequency;
- weekday;
- day_of_month;
- enabled;
- created_at;
- next_execution_at;
- last_triggered_at.

### PendingOrder

- ticker;
- amount_usd;
- dca_rule_id;
- status;
- idempotency_key;
- created_at;
- expires_at;
- executed_at;
- external_order_id.

### Alert

- type;
- symbol;
- operator;
- target_value;
- enabled;
- triggered;
- triggered_at.

### LocalTransaction

Solo guarda lo necesario para lógica local.

## 14. Seguridad

### Autorización

Único usuario permitido:

```env
TELEGRAM_ALLOWED_USER_ID=
```

Todo mensaje o callback de otro Telegram User ID debe rechazarse.

### Credenciales

Las credenciales viven en `.env`.

No se guardan API Keys de otros usuarios porque no existen otros usuarios.

### Trading

Por defecto:

```env
TRADING_ENABLED=false
```

### Logging

Sanitización obligatoria.

## 15. Testing

Prioridades:

1. OrderService.
2. Idempotencia.
3. DCA.
4. Authorization.
5. Scheduler.
6. Alerts.
7. Wallbit error handling.
8. Advisor.

No realizar requests reales durante tests.

Mockear:

- WallbitClient;
- AdvisorProvider;
- ExchangeProvider.

## 16. Deployment

La aplicación es una sola unidad.

Opciones:

```text
Docker → Azure VM
```

o:

```text
systemd → python main.py
```

No hay frontend de login.

No hay backend multiusuario.

No hay servicio de identidad.

## 17. Regla arquitectónica principal

Cada componente responde una sola pregunta:

```text
WallbitClient
¿Cómo hablo con Wallbit?

BalanceService
¿Cómo obtengo saldo?

PortfolioService
¿Cómo interpreto el portafolio?

DCAService
¿Cuándo corresponde una compra?

OrderService
¿Puede ejecutarse esta operación?

AlertService
¿Se alcanzó un umbral?

AdvisorService
¿Cómo explico o analizo los datos?

Telegram Handler
¿Cómo interactúa el usuario con esa función?
```

La arquitectura debe seguir siendo simple incluso cuando aumenten las funcionalidades.
