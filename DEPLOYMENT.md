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

## 4. Construir e iniciar

```bash
docker build -t wallbit-bot:local .
mkdir -p data
docker run -d \
  --name wallbit-bot \
  --restart unless-stopped \
  --env-file .env \
  -e DATABASE_URL=sqlite:////data/wallbit.db \
  -v "$PWD/data:/data" \
  wallbit-bot:local
```

Comprobar:

```bash
docker ps
docker logs --tail 100 wallbit-bot
docker exec wallbit-bot python -m app doctor
```

`doctor` nunca imprime tokens ni API keys. Puede consultar Wallbit usando una operación de
lectura para comprobar autenticación.

## 5. Backup SQLite

Detén brevemente el contenedor o usa una copia consistente desde el mismo host:

```bash
docker stop wallbit-bot
cp data/wallbit.db "data/wallbit.db.$(date +%Y%m%d-%H%M%S).bak"
docker start wallbit-bot
```

Guarda las copias fuera de la VM y prueba su restauración periódicamente. No las subas al
repositorio.

## 6. Actualizar

```bash
git pull --ff-only
docker build -t wallbit-bot:local .
docker rm -f wallbit-bot
docker run -d --name wallbit-bot --restart unless-stopped \
  --env-file .env -e DATABASE_URL=sqlite:////data/wallbit.db \
  -v "$PWD/data:/data" wallbit-bot:local
```

Antes de actualizar, haz backup de `data/wallbit.db`. Revisa `NIGHTLY_REPORT.md` y las notas
de versión si se introducen migraciones.
