# Wallbit Assistant Bot — Project Brief

## 1. Nombre del proyecto

**Wallbit Assistant Bot**

## 2. Resumen

Wallbit Assistant Bot es un bot personal de Telegram, open source y self-hosted, diseñado para conectarse a la API de Wallbit y ofrecer una capa de automatización, monitoreo, consulta y análisis financiero desde Telegram.

El proyecto está pensado exclusivamente como un **repositorio para uso personal**.

Cada persona que quiera utilizarlo debe:

1. clonar el repositorio;
2. crear su propio bot de Telegram;
3. configurar sus propias credenciales;
4. ejecutar su propia instancia.

No existe ni existirá dentro del alcance actual un sistema centralizado de usuarios, login, cuentas, almacenamiento de credenciales de terceros ni backend SaaS compartido.

## 3. Objetivo

El bot debe permitir:

- consultar saldo;
- revisar inversiones;
- recibir reportes automáticos;
- configurar alertas;
- gestionar estrategias DCA;
- confirmar operaciones desde Telegram;
- consultar historial;
- incorporar análisis mediante IA y Wallsync en versiones posteriores.

El valor principal del proyecto no es ser otra interfaz para Wallbit, sino una capa de:

- automatización;
- proactividad;
- personalización;
- notificaciones;
- control rápido desde Telegram.

## 4. Filosofía

Prioridades:

1. Seguridad.
2. Exactitud de datos.
3. Prevención de operaciones accidentales o duplicadas.
4. Simplicidad.
5. Modularidad.
6. Mantenibilidad.
7. UX.
8. Facilidad de despliegue.

No introducir infraestructura innecesaria.

## 5. Modelo de distribución

```text
GitHub
   ↓
Usuario clona el repositorio
   ↓
Copia .env.example → .env
   ↓
Configura Telegram
   ↓
Configura Wallbit
   ↓
Ejecuta su propia instancia
```

Cada instancia pertenece a una sola persona.

## 6. Fuera de alcance

No implementar:

- multiusuario;
- login;
- registro de cuentas;
- OAuth propio;
- panel de usuarios;
- almacenamiento de API Keys de terceros;
- backend SaaS compartido;
- administración central;
- roles;
- permisos por usuario;
- aislamiento entre cuentas;
- facturación;
- planes;
- organizaciones.

Si en el futuro se quisiera crear un SaaS, debe tratarse como otro producto o una rama separada, no como evolución obligatoria de este repositorio.

## 7. Stack

- Python 3.12+
- python-telegram-bot
- httpx
- SQLAlchemy
- SQLite
- APScheduler
- Pydantic / pydantic-settings
- pytest
- Ruff
- Docker
- GitHub Actions

FastAPI es opcional y solo debe utilizarse si aporta valor real para:

- health checks;
- webhooks;
- endpoints internos.

## 8. Configuración

Cada usuario configura su propia instancia mediante `.env`.

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USER_ID=

WALLBIT_API_KEY=
WALLBIT_BASE_URL=

DATABASE_URL=sqlite:///wallbit.db

DEFAULT_CURRENCY=CLP
DEFAULT_TIMEZONE=America/Santiago
DEFAULT_REPORT_TIME=09:00

TRADING_ENABLED=false

AI_ENABLED=false
WALLSYNC_ENABLED=false

LOG_LEVEL=INFO
```

Nunca guardar credenciales reales en Git.

`.env` debe estar en `.gitignore`.

## 9. V1

### `/saldo`

Consulta saldo disponible.

Puede mostrar, según disponibilidad real de la API:

- Checking;
- cash de inversión;
- disponible;
- patrimonio;
- conversión de moneda.

### `/inv`

Muestra el portafolio completo.

### `/inv TICKER`

Muestra una posición individual.

### `/dca`

Permite crear reglas recurrentes de compra.

La compra nunca se ejecuta automáticamente sin confirmación.

```text
Scheduler
   ↓
DCA pendiente
   ↓
Validación
   ↓
Telegram
   ↓
[Confirmar]
[Omitir]
   ↓
OrderService
   ↓
Wallbit
```

### `/alerta`

Alertas sobre:

- activos;
- tipos de cambio.

### `/historial`

Movimientos recientes.

### `/reporte`

Resumen financiero manual.

### Reporte automático

Envío diario a una hora configurable.

### `/config`

Configuración de:

- moneda;
- timezone;
- reporte;
- alertas;
- trading;
- IA.

## 10. Seguridad

### Usuario único

La instancia acepta únicamente:

```env
TELEGRAM_ALLOWED_USER_ID=
```

No existe concepto de múltiples usuarios.

### Trading

Por defecto:

```env
TRADING_ENABLED=false
```

El modo dry-run debe funcionar completamente sin ejecutar operaciones reales.

### Confirmación

Toda operación real requiere:

1. intención;
2. PendingOrder;
3. validación;
4. confirmación;
5. revalidación;
6. idempotencia;
7. ejecución.

### Idempotencia

Una misma operación nunca puede ejecutarse dos veces.

### Secrets

Nunca registrar:

- WALLBIT_API_KEY;
- TELEGRAM_BOT_TOKEN;
- Authorization headers;
- variables sensibles.

## 11. IA y Wallsync

La IA es opcional.

Debe utilizarse para:

- explicar portafolio;
- resumir rendimiento;
- analizar concentración;
- analizar riesgo;
- responder preguntas financieras contextuales;
- utilizar Wallsync si existe una integración oficial adecuada.

La IA nunca ejecuta trades directamente.

```text
Usuario
   ↓
AdvisorService
   ↓
IA / Wallsync
   ↓
Análisis
```

Si el usuario quiere actuar:

```text
Análisis
   ↓
intención
   ↓
PendingOrder
   ↓
confirmación
   ↓
OrderService
```

## 12. Restricciones

No introducir sin necesidad:

- microservicios;
- Kubernetes;
- Redis;
- colas distribuidas;
- múltiples bases de datos;
- frontend complejo;
- sistemas de login;
- autenticación web;
- gestión de usuarios;
- trading autónomo mediante IA.

## 13. Deploy

El proyecto debe poder desplegarse como una única aplicación.

Opciones:

- Azure VM;
- Docker;
- systemd;
- otro VPS Linux.

La prioridad es que una persona pueda mantener su propia instancia con facilidad.

## 14. Definición de éxito

Un usuario debe poder:

1. clonar el repositorio;
2. configurar `.env`;
3. ejecutar el bot;
4. consultar saldo;
5. consultar inversiones;
6. configurar DCA;
7. configurar alertas;
8. recibir reportes;
9. usar dry-run;
10. activar trading explícitamente;
11. añadir IA de manera opcional;
12. desplegar su instancia 24/7.

El proyecto debe seguir siendo entendible y mantenible por una sola persona.
