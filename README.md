# Wallbit Assistant Bot 🤖📈

**Wallbit Assistant Bot** es un bot personal de Telegram desarrollado en **Python 3.12+** que se conecta a la API pública de Wallbit para consultar saldos, portafolio de inversiones, cotizaciones, historial de movimientos y ejecutar compras recurrentes (DCA) mediante confirmación manual e idempotente.

Está construido como un **monolito modular con responsabilidades claramente separadas**, priorizando la **seguridad**, la **exactitud de datos**, la **idempotencia en compras** y la **prevención de órdenes accidentales o duplicadas**.

---

## 📑 Tabla de Contenidos

1. [Características Principales](#-características-principales)
2. [Arquitectura del Sistema](#-arquitectura-del-sistema)
3. [Comandos y Flujos](#-comandos-y-flujos)
4. [Requisitos Previos](#-requisitos-previos)
5. [Instalación](#-instalación)
6. [Configuración](#-configuración)
   - [Variables de Entorno](#variables-de-entorno)
   - [Crear Bot en Telegram con BotFather](#crear-bot-en-telegram-con-botfather)
   - [Obtener tu TELEGRAM_ALLOWED_USER_ID](#obtener-tu-telegram_allowed_user_id)
   - [Obtener tu API Key de Wallbit](#obtener-tu-api-key-de-wallbit)
7. [Modo Simulación / Dry-Run (Seguridad Financiera)](#-modo-simulación--dry-run-seguridad-financiera)
8. [Ejecución](#-ejecución)
9. [Pruebas Automatizadas (Tests)](#-pruebas-automatizadas-tests)
10. [Advertencia sobre Dinero Real](#-advertencia-sobre-dinero-real)

---

## 🚀 Características Principales

- 💰 **Consulta de Saldo (`/saldo`)**: Muestra cuenta Checking, Cash de inversión, Saldo disponible total y Patrimonio total, con conversión automática a moneda local (CLP, ARS, EUR, USDC, etc.).
- 📊 **Portafolio de Inversiones (`/inv` y `/inv [ticker]`)**: Vista consolidada y detalle por activo (acciones/ETFs), precio actual, títulos, costo base y rentabilidad sin inventar métricas si la API no las suministra.
- 📈 **Dollar-Cost Averaging Determinístico (`/dca`)**: Reglas de inversión programadas (semanales o mensuales) con **confirmación manual obligatoria** previa a cualquier compra.
- 🛡️ **Idempotencia Estricta**: Cada orden pendiente posee una clave única (`idempotency_key`) que previene doble ejecución por clics repetidos o problemas de red.
- 🔔 **Alertas de Precio y Divisa (`/alerta`)**: Monitoreo periódico en segundo plano con operadores `>=` y `<=`. Se marcan como disparadas para evitar notificaciones repetidas.
- ☀️ **Reporte Matutino Automático y Manual (`/reporte`)**: Resumen financiero enviado a la hora configurada (ej. 09:00 en tu zona horaria) que evita reportes duplicados al reiniciar la app.
- 🧾 **Historial de Movimientos (`/historial`)**: Consulta de transacciones de Wallbit complementadas con el registro local, con paginación interactiva.
- ⚙️ **Configuración Interactiva (`/config`)**: Personaliza moneda por defecto, hora matutina, zona horaria y verifica el estado de conexión con Wallbit mediante botones.
- 🔒 **Acceso Exclusivo y Sanitización de Logs**: Rechaza cualquier interacción de usuarios no autorizados (`TELEGRAM_ALLOWED_USER_ID`) y enmascara tokens y claves en todos los logs.

---

## 🏛 Arquitectura del Sistema

El bot sigue un diseño en capas desacoplado:

```
wallbit-bot/
├── app/
│   ├── core/           # Configuración (pydantic-settings), constantes, seguridad y logging
│   ├── db/             # Modelos SQLAlchemy, base de datos SQLite y repositorios
│   ├── wallbit/        # Cliente HTTP asíncrono (httpx), esquemas Pydantic y excepciones
│   ├── services/       # Lógica de negocio (Balance, Portfolio, DCA, Orders, Alerts, etc.)
│   ├── jobs/           # Scheduler centralizado (APScheduler) y tareas en segundo plano
│   ├── bot/            # Handlers, conversaciones, callbacks y teclados de Telegram
│   └── utils/          # Formateo monetario y utilidades de tiempo/zonas horarias
├── tests/              # Suite de pruebas unitarias y de integración (pytest)
├── main.py             # Punto de entrada principal
└── .env.example        # Plantilla de variables de entorno
```

### Flujo de Datos

```
Telegram User ──> Telegram Handler ──> Business Service ──> WallbitClient ──> Wallbit Public API
                         │                                 └──> Repositories  ──> SQLite Database
                         └───────> Inline Keyboards
```

---

## 💬 Comandos y Flujos

| Comando | Descripción |
| :--- | :--- |
| `/start` | Presentación, diagnóstico de conexión con Wallbit y menú de inicio |
| `/saldo` | Saldo en Checking, Cash de inversión, Disponible y conversión a moneda local |
| `/saldo [moneda]` | Saldo convertido a divisa específica (ej: `/saldo eur`, `/saldo ars`) |
| `/inv` | Resumen de todo tu portafolio de activos |
| `/inv [ticker]` | Detalle de posición individual (ej: `/inv voo`, `/inv aapl`) |
| `/dca` | Menú interactivo: Crear regla, ver reglas activas, ver pausadas |
| `/alerta` | Menú interactivo: Crear alerta (precio o divisa), ver mis alertas |
| `/historial` | Últimos movimientos con paginación `[⬅️ Anterior]` `[Siguiente ➡️]` |
| `/reporte` | Resumen financiero bajo demanda |
| `/config` | Configurar moneda, hora del reporte, zona horaria y alertas |
| `/cancel` | Cancelar cualquier conversación en curso |

---

## 📦 Requisitos Previos

- **Python 3.12 o superior**
- Cuenta activa en **Wallbit** con API Key generada
- Bot de Telegram registrado con **@BotFather**

---

## 🔧 Instalación

1. Clona el repositorio o navega a la carpeta del proyecto:
   ```bash
   cd wallbit-bot
   ```

2. Crea y activa un entorno virtual:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

---

## ⚙️ Configuración

Copia el archivo `.env.example` a `.env`:
```bash
cp .env.example .env
```

### Variables de Entorno

| Variable | Requerido | Descripción | Ejemplo |
| :--- | :---: | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | Sí | Token del bot de Telegram entregado por BotFather | `7123456789:AAH...` |
| `TELEGRAM_ALLOWED_USER_ID` | Sí | Tu ID numérico de Telegram (solo tú podrás usar el bot) | `123456789` |
| `WALLBIT_API_KEY` | Sí | Clave de API generada en Wallbit Dashboard | `wb_live_...` |
| `WALLBIT_BASE_URL` | No | URL base de la API pública de Wallbit | `https://api.wallbit.io` |
| `DATABASE_URL` | No | Conexión a la base de datos SQLite | `sqlite:///wallbit.db` |
| `DEFAULT_CURRENCY` | No | Moneda para conversiones locales (`CLP`, `USD`, `ARS`, `EUR`, `USDC`) | `CLP` |
| `DEFAULT_TIMEZONE` | No | Zona horaria IANA para reportes y ejecuciones | `America/Santiago` |
| `DEFAULT_REPORT_TIME` | No | Hora para el reporte diario matutino (HH:MM) | `09:00` |
| `TRADING_ENABLED` | No | `false` = modo simulación (recomendado); `true` = órdenes reales | `false` |
| `LOG_LEVEL` | No | Nivel de logging (`INFO`, `DEBUG`, `WARNING`, `ERROR`) | `INFO` |

### Crear Bot en Telegram con BotFather

1. Abre Telegram y busca a [@BotFather](https://t.me/BotFather).
2. Envía `/newbot` y sigue las instrucciones para elegir un nombre y un username (debe terminar en `bot`).
3. Copia el token de acceso generado y colócalo en `TELEGRAM_BOT_TOKEN`.

### Obtener tu TELEGRAM_ALLOWED_USER_ID

1. En Telegram, busca a [@userinfobot](https://t.me/userinfobot) o [@raw_data_bot](https://t.me/raw_data_bot).
2. Envía cualquier mensaje y te responderá con tu **Id** numérico (por ejemplo `123456789`).
3. Colócalo en `TELEGRAM_ALLOWED_USER_ID`.

### Obtener tu API Key de Wallbit

1. Ingresa a tu cuenta en [Wallbit](https://wallbit.io) desde la app o dashboard.
2. Ve a **Configuración → API Keys** (Settings → API Keys).
3. Genera una nueva API Key con permisos de lectura (`read`) y transacciones (`trade`).
4. Guarda la clave en `WALLBIT_API_KEY`.

---

## 🧪 Modo Simulación / Dry-Run (Seguridad Financiera)

Por defecto, el bot tiene configurado:

```env
TRADING_ENABLED=false
```

En este modo:
- **Ninguna orden real llega a Wallbit.**
- Puedes crear reglas DCA, recibir notificaciones y presionar **[Confirmar compra]**.
- El bot simula la compra generando un ID de prueba (`SIM-XXXXXXXX`) y registra la transacción en tu base de datos local:
  ```
  🧪 Modo simulación
  Se habría ejecutado:
  Compra VOO
  $50.00 USD
  Sim ID: SIM-A1B2C3D4
  ```
- **Solo cuando cambies `TRADING_ENABLED=true` se enviarán órdenes de compra reales al mercado.**

---

## ▶️ Ejecución

Para iniciar el bot:

```bash
python main.py
```

Al iniciarse:
- Se crearán automáticamente las tablas SQLite en `wallbit.db`.
- Se verificará la conexión a la API de Wallbit.
- Se levantará el scheduler centralizado con las tareas de reporte diario, DCA y alertas.
- Comenzará a escuchar tus mensajes en Telegram.

---

## 🧪 Pruebas Automatizadas (Tests)

El proyecto cuenta con una amplia suite de pruebas unitarias y de integración que mockea el cliente de Wallbit para garantizar que **nunca se efectúen operaciones reales durante las pruebas**.

Para correr todos los tests:

```bash
pytest
```

Para ver la salida detallada:

```bash
pytest -v
```

### Casos Cubiertos:
- Consulta y cálculo de saldos (`BalanceService`).
- Portafolio y cálculo de rentabilidad sin inventar métricas (`PortfolioService`).
- Creación y cálculo de fechas de DCA semanal y mensual (`DCAService`).
- Disparadores de DCA con saldo suficiente e insuficiente.
- Pausa, reactivación y eliminación de DCA.
- Confirmación de órdenes en modo simulación y real (`OrderService`).
- **Idempotencia estricta**: prevención de doble orden ante clics repetidos.
- Expiración de órdenes pendientes vencidas.
- Disparadores de alertas con operadores `>=` y `<=`, y prevención de disparo repetido.
- Resumen financiero matutino (`ReportService`).
- Seguridad: rechazo de usuarios no autorizados (`"Este bot es privado."`).
- Sanitización y enmascaramiento de tokens y secretos en logs.
- Manejo de códigos HTTP de Wallbit (400, 401, 404, 412, 422, 429).

---

## ⚠️ Advertencia sobre Dinero Real

> [!CAUTION]
> **Wallbit Assistant Bot** opera con servicios financieros reales.
> - Mantén siempre `TRADING_ENABLED=false` mientras pruebas el bot.
> - **Nunca compartas tu archivo `.env` ni tus API Keys.**
> - El bot **no realiza recomendaciones financieras ni asesoramiento de inversión**; únicamente presenta información de tu cuenta y ejecuta instrucciones explícitas y determinísticas que confirmas manualmente.
