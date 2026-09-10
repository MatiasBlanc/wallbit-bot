# Despliegue en una VM Linux de Azure

Wallbit Assistant Bot se despliega como una única instancia self-hosted. No uses varias réplicas
con SQLite ni compartas el `.env`.

## 1. Crear la VM

Crea una VM Linux pequeña (Ubuntu LTS), restringe SSH a tu IP y no expongas puertos que la
aplicación no necesite. El bot usa polling, por lo que no requiere un puerto HTTP público.

## 2. Instalar Docker y clonar

```bash
sudo apt update
sudo apt install -y docker.io git
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
# Cierra y vuelve a abrir la sesión SSH después de este comando
git clone <URL_DEL_REPOSITORIO> wallbit-bot
cd wallbit-bot
```

## 3. Configurar secretos

```bash
cp .env.example .env
chmod 600 .env
$EDITOR .env
```

Configura `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USER_ID`, `WALLBIT_API_KEY` y deja
`TRADING_ENABLED=false` mientras validas la instalación. No guardes secretos en imágenes,
logs ni el repositorio.

## 4. Construir e iniciar con Docker Compose

```bash
docker compose up -d --build
```

Compose crea el volumen administrado `wallbit-data`, escribible por el usuario no root del contenedor.

O si prefieres usar `docker run` directamente:

```bash
docker build -t wallbit-bot:local .
docker run -d \
  --name wallbit-bot \
  --restart unless-stopped \
  --env-file .env \
  -e DATABASE_URL=sqlite:////data/wallbit.db \
  -v wallbit-data:/data \
  wallbit-bot:local
```

Comprobar:

```bash
docker compose ps
docker compose logs --tail 100
docker exec wallbit-bot python -m app doctor
```

`doctor` nunca imprime tokens ni API keys. Valida el token con Telegram y consulta Wallbit mediante
una operación de lectura. En Telegram puedes usar `/estado` para ver métricas en vivo.

## 5. Backup SQLite (En caliente / Atómico)

El bot incluye respaldo atómico mediante la API nativa de SQLite sin necesidad de detener el contenedor:

```bash
# Ejecutar respaldo atómico dentro del contenedor:
docker exec wallbit-bot python -m app backup --dir /data/backups --keep 7
```

O mediante un cron en el host (`crontab -e`):

```bash
# Respaldo diario a las 03:00 AM con rotación automática de las últimas 7 copias:
0 3 * * * docker exec wallbit-bot python -m app backup --dir /data/backups --keep 7
```

Extrae periódicamente las copias del volumen y guárdalas fuera de la VM (por ejemplo en Azure Blob Storage o S3):

```bash
docker cp wallbit-bot:/data/backups ./backups-export
```

Prueba su restauración periódicamente y no las subas al repositorio.

## 6. Actualizar

Primero ejecuta y exporta un backup. Si desplegaste con Compose:

```bash
docker exec wallbit-bot python -m app backup --dir /data/backups --keep 7
docker cp wallbit-bot:/data/backups ./backups-export
git pull --ff-only
docker compose up -d --build
docker exec wallbit-bot python -m app doctor
```

Si usaste `docker run`, vuelve a crear el contenedor con el mismo volumen `wallbit-data` mostrado en
la sección 4. Revisa las notas de versión antes de aplicar migraciones.
