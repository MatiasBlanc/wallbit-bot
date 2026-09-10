# Guía de Contribución

¡Gracias por tu interés en contribuir a **Wallbit Assistant Bot**! 🎉

Este documento describe las pautas y el proceso para contribuir al proyecto.

## Código de Conducta

Al participar en este proyecto, aceptás respetar nuestro [Código de Conducta](CODE_OF_CONDUCT.md). Por favor, leelo antes de contribuir.

## ¿Cómo puedo contribuir?

### 🐛 Reportar Bugs

Si encontraste un bug, por favor [abrí un issue](../../issues/new?template=bug_report.md) incluyendo:

- Una descripción clara del problema
- Pasos para reproducirlo
- Comportamiento esperado vs. comportamiento actual
- Versión de Python y sistema operativo
- Logs relevantes (asegurate de **no incluir API keys ni datos sensibles**)

### 💡 Sugerir Mejoras

¿Tenés una idea para mejorar el bot? [Abrí un feature request](../../issues/new?template=feature_request.md) describiendo:

- El problema que resolvería
- Tu solución propuesta
- Alternativas que consideraste

### 🔧 Enviar Código

1. **Forkeá** el repositorio
2. **Creá una rama** desde `main`:
   ```bash
   git checkout -b feature/mi-nueva-funcionalidad
   ```
3. **Hacé tus cambios** siguiendo las convenciones del proyecto
4. **Ejecutá los tests**:
   ```bash
   pytest
   ```
5. **Verificá el linting**:
   ```bash
   ruff check .
   ```
6. **Commiteá** usando [Conventional Commits](https://www.conventionalcommits.org/):
   ```bash
   git commit -m "feat: agregar soporte para nueva funcionalidad"
   ```
7. **Pusheá** tu rama y **abrí un Pull Request**

## Configuración del Entorno de Desarrollo

### Requisitos previos

- Python 3.12+
- pip

### Instalación

```bash
# Clonar el repositorio
git clone https://github.com/MatiasBlanc/wallbit-bot.git
cd wallbit-bot

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# Instalar dependencias
pip install -r requirements.txt

# Copiar y configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales
```

### Ejecutar tests

```bash
# Todos los tests
pytest

# Un test específico
pytest tests/modules/balance/test_balance_service.py -v
```

### Linting

```bash
# Verificar estilo
ruff check .

# Corregir automáticamente
ruff check . --fix
```

## Convenciones de Código

### Estilo

- Seguimos las reglas configuradas en `pyproject.toml` con **Ruff**
- Línea máxima: 120 caracteres
- Usamos **type hints** siempre que sea posible
- Docstrings en español para funciones públicas
- Cada funcionalidad vive en `app/modules/<dominio>/`, con sus pruebas en `tests/modules/<dominio>/`
- Los componentes externos van en `app/infrastructure/`; las utilidades compartidas, en `app/shared/`
- Registra las rutas en `app/bot/registry.py` y los nuevos modelos ORM en `register_models()` de `app/infrastructure/database/database.py`

### Estructura de commits

Usamos [Conventional Commits](https://www.conventionalcommits.org/):

| Prefijo    | Uso                                      |
|------------|------------------------------------------|
| `feat:`    | Nueva funcionalidad                      |
| `fix:`     | Corrección de bug                        |
| `docs:`    | Cambios en documentación                 |
| `test:`    | Agregar o modificar tests                |
| `refactor:`| Refactorización sin cambio funcional     |
| `chore:`   | Tareas de mantenimiento                  |
| `style:`   | Cambios de formato (sin cambio lógico)   |

### Ramas

- `main` — rama principal, siempre estable
- `feature/nombre` — nuevas funcionalidades
- `fix/nombre` — correcciones de bugs
- `docs/nombre` — cambios de documentación

## Pull Requests

- Cada PR debe estar asociado a un issue cuando sea posible
- Los PRs deben pasar todos los tests y el linting
- Incluí una descripción clara de los cambios
- Si tu PR incluye cambios visuales o de UX en el bot, incluí capturas de pantalla
- Los PRs son revisados antes de ser mergeados

## Seguridad

Si descubrís una vulnerabilidad de seguridad, **NO la reportes como un issue público**. En su lugar, seguí las instrucciones en [SECURITY.md](SECURITY.md).

## ¿Preguntas?

Si tenés dudas sobre cómo contribuir, no dudes en [abrir un issue](../../issues/new) con tu pregunta. ¡Estamos para ayudar!

---

¡Gracias por ayudar a mejorar Wallbit Assistant Bot! 🚀
