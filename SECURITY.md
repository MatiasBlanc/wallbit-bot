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

- La API key se obtiene exclusivamente del entorno local de la instancia.
- Nunca se solicitan API keys ni contraseñas de Wallbit por Telegram.
- Los logs sanitizan secretos conocidos, excepciones y objetos anidados. No deben registrarse cuerpos de actualizaciones ni credenciales.
- El archivo `.env` está incluido en `.gitignore` y **nunca** debe ser commiteado
- Se provee `.env.example` como plantilla sin datos reales

### Acceso al bot

- El bot está restringido a un único usuario mediante `TELEGRAM_ALLOWED_USER_ID`.
- `@restricted` protege comandos y callbacks financieros.
- No existe login, registro, OAuth ni almacenamiento de credenciales de terceros.
- Los usuarios sin autorización reciben un rechazo explícito y los callbacks de modificación vuelven a verificar la propiedad del registro.

### Operaciones financieras

- Por defecto, el modo trading está **deshabilitado** (`TRADING_ENABLED=false`)
- Todas las compras requieren **confirmación manual** del usuario
- Las órdenes POST a la API **nunca** se reintentan automáticamente.
- Un resultado incierto requiere revisión manual mediante `/ordenes`.
- Las órdenes interrumpidas durante un reinicio se recuperan en estado de verificación.
- Las órdenes pendientes expiran automáticamente tras un período configurable.

### Base de datos

- SQLite se usa como almacenamiento local (no accesible remotamente)
- No se almacenan contraseñas ni API keys en SQLite; las credenciales permanecen en el entorno.
- El despliegue requiere una única réplica y almacenamiento persistente con copias de seguridad.

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
