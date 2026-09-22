<div align="center">

# Wallbit Assistant Bot

### Tu cuenta de Wallbit, monitoreada desde Telegram

Consulta saldos e inversiones, configura alertas y DCA, recibe reportes automáticos y analiza tu cartera con IA opcional; todo desde una instancia privada que tú controlas.

[![CI](https://github.com/MatiasBlanc/wallbit-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/MatiasBlanc/wallbit-bot/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](Dockerfile)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Privado por defecto · Self-hosted · Una persona por instancia · Trading desactivado inicialmente**

</div>

> [!IMPORTANT]
> Este es un proyecto comunitario y **no es un producto oficial de Wallbit**. No ofrece asesoramiento financiero. Empieza siempre con `TRADING_ENABLED=false`: así puedes probar todo el flujo sin enviar compras reales.

---

## ¿Qué puedes hacer?

| Función | Qué obtienes |
|---|---|
| 💰 **Saldo** | Checking, cash de inversión, disponible, patrimonio y conversión de moneda |
| 📊 **Portafolio** | Posiciones, precio actual, costo conocido y rentabilidad disponible |
| 📅 **DCA** | Reglas semanales o mensuales que siempre piden confirmación antes de comprar |
| 🔔 **Alertas** | Avisos de precio de acciones/ETF y tipos de cambio |
| ☀️ **Reportes** | Resumen financiero manual y envío diario programado |
| 🧾 **Historial** | Movimientos de Wallbit complementados con operaciones locales |
| 🤖 **Advisor IA** | Análisis de riesgo, concentración y rendimiento con Gemini u OpenAI |
| 🛡️ **Órdenes seguras** | Idempotencia local, expiración y reconciliación tras timeouts |
| 📈 **Estado** | Uptime, salud de jobs, llamadas a Wallbit y latencia media |
| 💾 **Backups** | Copias atómicas de SQLite sin detener el bot |

## Cómo funciona

```text
Telegram
   │
   ├── Consultas ───────────────► Wallbit API (solo lectura)
   │
   ├── DCA programado
   │      └──► Orden pendiente ─► Confirmación en Telegram
   │                                  ├── Simulación (por defecto)
   │                                  └── Compra real (opt-in)
   │
   └── Alertas / reportes ──────► APScheduler
                                      │
                                      └── Estado local en SQLite
```

El bot usa **polling**, por lo que no necesita dominio, webhook ni puerto HTTP público.

---

## Inicio rápido con Docker — recomendado

### 1. Requisitos

- Una cuenta de [Wallbit](https://wallbit.io) con acceso a su API pública.
- Un bot de Telegram creado con [@BotFather](https://t.me/BotFather).
- Tu ID numérico de Telegram.
- Docker con Docker Compose.

### 2. Clona y configura

```bash
git clone https://github.com/MatiasBlanc/wallbit-bot.git
cd wallbit-bot
cp .env.example .env
chmod 600 .env
```

Edita `.env` y completa como mínimo:

```env
TELEGRAM_BOT_TOKEN=token_entregado_por_botfather
TELEGRAM_ALLOWED_USER_ID=123456789
WALLBIT_API_KEY=tu_api_key_de_wallbit

# Mantén este valor durante todas las pruebas iniciales.
TRADING_ENABLED=false
```

> [!WARNING]
> No pegues secretos en issues, capturas, mensajes de Telegram ni archivos versionados. `.env` ya está ignorado por Git.

### 3. Construye y valida

```bash
docker compose build
docker compose run --rm wallbit-bot python -m app doctor
```

Una instalación correcta muestra:

```text
Telegram        OK
Wallbit         OK
Database        OK
Scheduler       OK
AI              DISABLED
Trading         DISABLED
```

`doctor` valida el token con Telegram, realiza una consulta de lectura a Wallbit y comprueba SQLite y APScheduler. Nunca imprime tus secretos.

### 4. Inicia el bot

```bash
docker compose up -d
docker compose logs -f --tail 100
```

Abre tu bot en Telegram y envía:

```text
/start
```

Docker Compose conserva la base en el volumen `wallbit-data` y reinicia el contenedor automáticamente salvo que lo detengas explícitamente.

---

## Configuración de Telegram y Wallbit

### Crear el bot con BotFather

1. Abre [@BotFather](https://t.me/BotFather).
2. Envía `/newbot`.
3. Elige un nombre y un usuario terminado en `bot`.
4. Copia el token en `TELEGRAM_BOT_TOKEN`.
5. Opcionalmente, usa `/setcommands` y registra:

```text
start - Abrir Wallbit Assistant
saldo - Consultar saldo
inv - Ver portafolio
reporte - Generar resumen
historial - Ver movimientos
dca - Gestionar compras periódicas
alerta - Gestionar alertas
analizar - Analizar cartera con IA
ordenes - Revisar órdenes inciertas
estado - Ver estado del sistema
config - Abrir configuración
cancel - Cancelar el flujo actual
```

### Obtener tu ID de Telegram

Consulta tu ID numérico con un bot de información de usuario, por ejemplo `@userinfobot`, y guárdalo en `TELEGRAM_ALLOWED_USER_ID`.

La instancia rechaza mensajes y callbacks de cualquier otro usuario con `Este bot es privado.` También rechaza toda interacción fuera de un chat privado, incluso si el usuario autorizado añadió el bot a un grupo.

### Configurar Wallbit

Genera una API key desde las opciones disponibles en tu cuenta de Wallbit y guárdala únicamente en `WALLBIT_API_KEY`.

- Para empezar, usa permisos mínimos de lectura y `TRADING_ENABLED=false`.
- Habilita permisos de compra solamente cuando hayas validado el bot en simulación.
- Si revocas o rotas la key, actualiza `.env`, reinicia el contenedor y ejecuta `doctor` otra vez.

---

## Tus primeros 10 minutos

Una vez iniciado el bot, prueba este recorrido:

1. `/start` — comprueba que Wallbit figure conectado.
2. `/saldo` — revisa el disponible y la moneda local.
3. `/inv` — consulta el portafolio completo.
4. `/inv VOO` — abre el detalle de una posición.
5. `/reporte` — genera el resumen financiero.
6. `/config` — ajusta moneda, zona horaria y hora del reporte.
7. `/alerta` — crea una alerta de prueba.
8. `/dca` — crea una regla pequeña en simulación.
9. Cuando llegue la propuesta DCA, pulsa **Comprar**: recibirás un ID `SIM-...` y no se enviará nada a Wallbit.
10. `/estado` — verifica jobs, uptime y latencias.

---

## Comandos

| Comando | Uso |
|---|---|
| `/start` | Presentación, modo actual, conexión y menú principal |
| `/saldo` | Saldo en la moneda configurada |
| `/saldo EUR` | Saldo convertido a una moneda soportada |
| `/inv` | Resumen del portafolio |
| `/inv AAPL` | Detalle de una posición concreta |
| `/dca` | Crear, listar, pausar, reactivar o eliminar reglas DCA |
| `/alerta` | Crear, listar o borrar alertas de precio y FX |
| `/historial` | Movimientos recientes con paginación |
| `/reporte` | Resumen financiero bajo demanda |
| `/analizar` | Menú de análisis IA de solo lectura |
| `/analizar ¿Qué riesgo tiene mi cartera?` | Pregunta libre al advisor |
| `/ordenes` | Revisar resultados inciertos después de un timeout |
| `/estado` o `/status` | Métricas y estado de tareas en segundo plano |
| `/config` | Moneda, zona horaria, reporte y alertas |
| `/cancel` | Cancelar una conversación activa |

### DCA: automatización sin trading autónomo

Una regla DCA no compra por sí sola:

```text
Fecha programada
      ↓
Se verifican saldo y cotización
      ↓
Telegram muestra monto + comisión estimada
      ↓
[Comprar]                    [Ahora no]
      ↓
Se vuelven a validar los fondos
      ↓
Simulación o envío único a Wallbit
```

Cada intención tiene vencimiento y una clave idempotente local. Los clics repetidos no ejecutan la misma orden dos veces. Si Telegram no está disponible, las propuestas DCA y alertas quedan en una cola local y se reintentan automáticamente; consulta `/ordenes` para ver compras que aún esperan confirmación.

### ¿Qué pasa si Wallbit responde con timeout?

Un timeout o error 5xx no demuestra si una compra fue aceptada. Por eso el bot:

1. **no reintenta automáticamente**;
2. marca la orden como `verification_required`;
3. te pide revisar primero tu cuenta de Wallbit;
4. permite registrar el resultado mediante `/ordenes` sin enviar otra compra.

Las órdenes que estaban en proceso durante un reinicio también pasan a revisión manual.

---

## Simulación y trading real

### Modo seguro

```env
TRADING_ENABLED=false
```

En simulación puedes usar DCA, confirmaciones, historial y reportes. Al confirmar una propuesta se genera una referencia `SIM-XXXXXXXX`, pero **no se llama al endpoint de compra**.

### Activar compras reales

> [!CAUTION]
> Activa esta opción solo después de completar el recorrido de prueba, verificar tus permisos y entender la reconciliación de órdenes.

```env
TRADING_ENABLED=true
```

Reinicia y confirma el estado:

```bash
docker compose up -d
docker exec wallbit-bot python -m app doctor
```

Toda compra real continúa necesitando una confirmación explícita en Telegram. El advisor IA no puede comprar, vender ni confirmar operaciones.

---

## Advisor con IA — opcional

La IA está desactivada por defecto y solo recibe datos financieros estructurados de lectura. No tiene acceso directo al cliente de trading ni existe una herramienta `execute_trade`.

### Probar el flujo sin proveedor externo

```env
AI_ENABLED=true
AI_PROVIDER=mock
```

### Google Gemini

```env
AI_ENABLED=true
AI_PROVIDER=gemini
AI_API_KEY=tu_api_key
AI_MODEL=gemini-2.5-flash
```

### OpenAI o API compatible

```env
AI_ENABLED=true
AI_PROVIDER=openai
AI_API_KEY=tu_api_key
AI_MODEL=gpt-4o-mini
# AI_BASE_URL=https://api.openai.com/v1
```

Después de editar `.env`:

```bash
docker compose up -d
```

Usa `/analizar` para resumen, riesgo, concentración o rendimiento. `WALLSYNC_ENABLED` debe permanecer en `false` mientras no exista una integración programática oficial configurada.

---

## Instalación sin Docker

```bash
git clone https://github.com/MatiasBlanc/wallbit-bot.git
cd wallbit-bot
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
# Edita .env
python -m app doctor
python main.py
```

En Windows PowerShell, activa el entorno con:

```powershell
.venv\Scripts\Activate.ps1
```

Para mantener esta instalación activa 24/7, usa un servicio `systemd` o un supervisor equivalente. La guía principal de servidor está en [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Variables de entorno

<details>
<summary><strong>Ver referencia completa</strong></summary>

| Variable | Obligatoria | Valor inicial | Descripción |
|---|:---:|---|---|
| `TELEGRAM_BOT_TOKEN` | Sí | — | Token entregado por BotFather |
| `TELEGRAM_ALLOWED_USER_ID` | Sí | — | Único usuario autorizado |
| `WALLBIT_API_KEY` | Sí | — | Credencial local para la API pública de Wallbit |
| `WALLBIT_BASE_URL` | No | `https://api.wallbit.io` | URL HTTPS de Wallbit |
| `WALLBIT_PLAN` | No | `classic` | Plan usado para estimar comisión: `classic`, `pro` o `max` |
| `WALLBIT_MAX_CONCURRENT_REQUESTS` | No | `4` | Máximo de lecturas Wallbit simultáneas |
| `WALLBIT_CACHE_TTL_SECONDS` | No | `5` | Caché corta de cotizaciones y metadata |
| `DATABASE_URL` | No | `sqlite:///wallbit.db` | URL de SQLite; Compose la dirige a `/data` |
| `DEFAULT_CURRENCY` | No | `CLP` | Moneda inicial: CLP, USD, ARS, EUR o USDC |
| `DEFAULT_TIMEZONE` | No | `America/Santiago` | Zona horaria IANA |
| `DEFAULT_REPORT_TIME` | No | `09:00` | Hora local del reporte diario |
| `TRADING_ENABLED` | No | `false` | Habilita compras reales únicamente al usar `true` |
| `AI_ENABLED` | No | `false` | Activa `/analizar` |
| `AI_PROVIDER` | No | `mock` | `mock`, `gemini` u `openai` |
| `AI_API_KEY` | Según provider | — | Key de Gemini/OpenAI |
| `AI_MODEL` | No | — | Modelo solicitado al proveedor |
| `AI_BASE_URL` | No | OpenAI oficial | Endpoint compatible personalizado |
| `WALLSYNC_ENABLED` | No | `false` | Reserva para integración oficial |
| `FX_CACHE_TTL_SECONDS` | No | `300` | Caché de tipos de cambio |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING` o `ERROR` |
| `ALERT_CHECK_INTERVAL_MINUTES` | No | `5` | Frecuencia de revisión de alertas |
| `DCA_CHECK_INTERVAL_MINUTES` | No | `1` | Frecuencia de revisión de DCA |
| `ORDER_EXPIRY_HOURS` | No | `24` | Vigencia de una confirmación pendiente |

</details>

---

## Operación 24/7

### Estado y logs

```bash
docker compose ps
docker compose logs --tail 100
docker exec wallbit-bot python -m app doctor
```

Dentro de Telegram:

```text
/estado
```

### Backup atómico

```bash
docker exec wallbit-bot \
  python -m app backup --dir /data/backups --keep 7
# Verifica la integridad antes de exportar o restaurar una copia.
docker exec wallbit-bot \
  python -m app verify-backup --file /data/backups/wallbit_backup_YYYYMMDD_HHMMSS_ffffff.db
```

Exporta las copias fuera del servidor:

```bash
docker cp wallbit-bot:/data/backups ./backups-export
```

Un cron diario de ejemplo:

```cron
0 3 * * * docker exec wallbit-bot python -m app backup --dir /data/backups --keep 7
```

### Actualizar

```bash
docker exec wallbit-bot python -m app backup --dir /data/backups --keep 7
git pull --ff-only
docker compose up -d --build
docker exec wallbit-bot python -m app doctor
```

SQLite requiere **una sola réplica**. No levantes varios contenedores del bot contra la misma base.

---

## Solución de problemas

<details>
<summary><strong>Telegram aparece como ERROR en doctor</strong></summary>

- Comprueba que copiaste el token completo y sin comillas.
- Verifica que el bot no haya sido revocado en BotFather.
- Confirma que el servidor tiene salida HTTPS hacia Telegram.
- Vuelve a ejecutar `docker compose run --rm wallbit-bot python -m app doctor`.

</details>

<details>
<summary><strong>Wallbit aparece como ERROR</strong></summary>

- Revisa `WALLBIT_API_KEY` y `WALLBIT_BASE_URL`.
- Confirma que la key está activa y tiene permisos de lectura.
- Revisa los logs sin compartir la key.
- Si rotaste la credencial, recrea el contenedor con `docker compose up -d`.

</details>

<details>
<summary><strong>El bot responde “Este bot es privado”</strong></summary>

El ID del remitente no coincide con `TELEGRAM_ALLOWED_USER_ID`. Corrige el valor en `.env` y reinicia.

</details>

<details>
<summary><strong>No llegan DCA, alertas o reportes</strong></summary>

- Ejecuta `/estado` y revisa el último estado de cada job.
- Comprueba zona horaria y hora desde `/config`.
- Verifica que la regla o alerta siga activa.
- Consulta `docker compose logs --tail 200`.

</details>

<details>
<summary><strong>Una compra quedó sin resultado</strong></summary>

No la repitas. Revisa primero Wallbit y luego usa `/ordenes` para marcar si fue ejecutada o no.

</details>

<details>
<summary><strong>SQLite no persiste tras recrear el contenedor</strong></summary>

Usa `docker-compose.yml` sin retirar el volumen `wallbit-data`. Comprueba su existencia con `docker volume inspect wallbit-data`.

</details>

---

## Arquitectura y seguridad

El proyecto es un **monolito modular** pensado para una persona por instancia:

```text
app/
├── bot/                    # Registro y ciclo de vida de Telegram
├── core/                   # Configuración, autorización y logging seguro
├── infrastructure/
│   ├── database/           # SQLite, sesiones, migraciones y backups
│   ├── monitoring/         # Métricas en memoria
│   ├── scheduler/          # APScheduler
│   └── wallbit/            # Cliente HTTP y schemas externos
├── modules/
│   ├── advisor/            # IA opcional de solo lectura
│   ├── alerts/             # Alertas de activos y FX
│   ├── balance/            # Saldos
│   ├── dca/                # Reglas periódicas
│   ├── history/            # Movimientos locales/remotos
│   ├── orders/             # Confirmación y reconciliación
│   ├── portfolio/          # Inversiones
│   ├── reports/            # Resúmenes manuales/diarios
│   └── settings/           # Preferencias
└── shared/                 # Fechas, concurrencia, formato y FX
```

Controles principales:

- autorización global por `TELEGRAM_ALLOWED_USER_ID`;
- trading desactivado por defecto;
- confirmación manual y revalidación de fondos;
- transición atómica para evitar dobles clics;
- cero retries automáticos en compras;
- recuperación de órdenes interrumpidas;
- sanitización de tokens, API keys y tracebacks;
- secretos fuera de la imagen y del repositorio;
- IA aislada de las operaciones financieras.

Más detalles en [ARCHITECTURE.md](ARCHITECTURE.md), [SECURITY.md](SECURITY.md) y [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Desarrollo

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
ruff check .
mypy app main.py
```

La suite usa mocks de Wallbit y mantiene `TRADING_ENABLED=false`; no realiza compras reales. Para validar el contrato de lectura contra una cuenta de staging o con permisos solo lectura, sin crear órdenes:

```bash
RUN_WALLBIT_INTEGRATION=1 pytest -q tests/integration
```

No ejecutes esa prueba con una key que tenga permisos de trading.

Lee [CONTRIBUTING.md](CONTRIBUTING.md) antes de abrir un pull request. Las vulnerabilidades deben reportarse de forma privada siguiendo [SECURITY.md](SECURITY.md).

---

## Aviso financiero

> [!CAUTION]
> Este software se entrega sin garantías. Tú eres responsable de custodiar tus credenciales, revisar montos, permisos, comisiones y resultados antes de operar. Las comisiones mostradas son estimaciones locales; Wallbit determina el cargo final. Ningún texto generado por el bot o por un modelo de IA constituye asesoramiento financiero.

## Licencia

Distribuido bajo la licencia [MIT](LICENSE).

<div align="center">

Hecho para automatizar lo repetitivo sin ceder el control de cada compra.

</div>
