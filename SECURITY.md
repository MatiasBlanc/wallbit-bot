# Política de Seguridad

## Versiones Soportadas

| Versión | Soportada          |
|---------|--------------------|
| 1.0.x   | ✅ Sí              |

## Reportar una Vulnerabilidad

La seguridad de Wallbit Assistant Bot es una prioridad. Este bot maneja API keys financieras, por lo que tomamos muy en serio cualquier reporte de vulnerabilidad.

### ⚠️ NO reportes vulnerabilidades de seguridad como issues públicos

Si descubrís una vulnerabilidad de seguridad, por favor seguí estos pasos:

1. **Enviá un email** a la dirección de contacto del repositorio, o
2. **Usá la funcionalidad de "Security Advisories"** de GitHub en la pestaña "Security" del repositorio

### ¿Qué incluir en tu reporte?

- Descripción detallada de la vulnerabilidad
- Pasos para reproducirla
- Impacto potencial
- Si es posible, una sugerencia de solución

### ¿Qué esperar?

- **Confirmación** de recepción dentro de 48 horas
- **Evaluación inicial** dentro de 7 días
- **Actualización de estado** al menos cada 7 días hasta la resolución
- **Crédito público** (si lo deseás) una vez que el fix sea publicado

## Prácticas de Seguridad del Proyecto

### Datos sensibles

- En modo privado la API key se obtiene del entorno; en multiusuario se introduce desde una terminal privada y se almacena **cifrada con Fernet**.
- `CREDENTIAL_ENCRYPTION_KEY` debe mantenerse fuera de la base de datos, con backup separado y acceso restringido. Quien controle servidor y clave podrá descifrar las credenciales.
- Nunca se solicitan API keys ni contraseñas de Wallbit por Telegram. El login usa códigos temporales ligados a un ID, almacenados como hash y consumidos atómicamente.
- Los logs sanitizan secretos conocidos y la credencial del contexto activo; el formatter también sanitiza excepciones y objetos anidados. No se deben registrar cuerpos de actualizaciones ni credenciales fuera del contexto.
- El archivo `.env` está incluido en `.gitignore` y **nunca** debe ser commiteado
- Se provee `.env.example` como plantilla sin datos reales

### Acceso al bot

- Por defecto el bot está restringido a un usuario mediante `TELEGRAM_ALLOWED_USER_ID`.
- Con `MULTI_USER_ENABLED=true`, Telegram identifica al usuario y `/login` vincula su credencial individual. Las consultas financieras solo se aceptan en chats privados; nunca se utiliza la API key global como fallback.
- `@restricted` protege las rutas financieras. `/login` y `/logout` son rutas públicas que solo operan sobre el ID del remitente.
- Los códigos vencen, son de un uso y solo sirven para el destinatario. Las sesiones permanecen activas hasta `/logout`; no se implementa OAuth ni autenticación web.
- `/logout` desactiva la cuenta, pausa automatizaciones y expira pendientes, pero conserva historial y credencial cifrada. Revocar definitivamente la API key requiere hacerlo también en Wallbit; las solicitudes ya en curso pueden terminar.
- Los usuarios sin autorización reciben un rechazo explícito. Los callbacks de modificación verifican la propiedad del registro.

### Operaciones financieras

- Por defecto, el modo trading está **deshabilitado** (`TRADING_ENABLED=false`)
- Todas las compras requieren **confirmación manual** del usuario
- El modo multiusuario bloquea las compras reales, incluso si se intenta invocar directamente al cliente HTTP, hasta implementar reconciliación externa.
- Las órdenes POST a la API **nunca** se reintentan automáticamente
- Las órdenes pendientes expiran automáticamente tras un período configurable

### Base de datos

- SQLite se usa como almacenamiento local (no accesible remotamente)
- No se almacenan contraseñas ni API keys **en texto plano**. El modo multiusuario añade credenciales cifradas en `wallbit_credentials`.
- Usa una base nueva al migrar del modo privado: no se vinculan automáticamente registros antiguos a una cuenta externa no verificada.
- El despliegue actual requiere una única réplica y almacenamiento persistente con copias de seguridad.

## Dependencias

Recomendamos mantener las dependencias actualizadas regularmente:

```bash
pip install --upgrade -r requirements.txt
```

Considerá usar herramientas como [pip-audit](https://github.com/pypa/pip-audit) para verificar vulnerabilidades conocidas:

```bash
pip install pip-audit
pip-audit
```
