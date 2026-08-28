# Snaider Backend

Este proyecto corre con Django y PostgreSQL. La forma recomendada de levantar el backend en local es usando Docker Compose.

## Requisitos

- Docker
- Docker Compose
- Git

## 1) Clonar el repositorio

```bash
git clone https://github.com/Sh1zukku/ProyectoSnaiderBackend.git
cd ProyectoSnaiderBackend
```

## 2) Crear archivo .env

Crea un archivo `.env` en la raíz del proyecto con este contenido:

```env
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=
DB_HOST=db
DB_PORT=
```

> Importante: `DB_HOST` debe ser `db` porque ese es el nombre del servicio PostgreSQL en `docker-compose.yaml`.

## 3) Levantar los contenedores

Desde la raíz del proyecto ejecuta:

```bash
docker compose up --build
```

Esto va a:

- construir la imagen del backend Django
- crear el contenedor de PostgreSQL
- levantar la API en el puerto `8000`

## 4) Verificar que el backend quedó levantado

Abre en tu navegador o usa curl:

```bash
http://localhost:8000
```

O:

```bash
curl http://localhost:8000
```

Si la app responde correctamente, el backend está corriendo.

## 5) Ejecutar migraciones

En una terminal nueva, ejecuta:

```bash
docker compose exec web python manage.py migrate
```

Si querés crear un usuario administrador:

```bash
docker compose exec web python manage.py createsuperuser
```

## 6) Reiniciar el proyecto

Si ya tenés los contenedores creados y querés volver a levantarlos:

```bash
docker compose up
```

Para detenerlos:

```bash
docker compose down
```

Para borrar también la base de datos persistente:

```bash
docker compose down -v
```

## 7) Estructura importante

- `Dockerfile`: define la imagen de la API Django
- `docker-compose.yaml`: orquesta backend + base de datos
- `snaiderbackend/`: código del proyecto Django

## 8) Solución rápida de errores comunes

### Error de conexión a PostgreSQL

Verificá que en el `.env` existan estas variables:

```env
POSTGRES_DB=snaider_db
POSTGRES_USER=snaider_user
POSTGRES_PASSWORD=snaider_password
DB_HOST=db
DB_PORT=5432
```

### El contenedor no inicia

Rebuild completo:

```bash
docker compose down -v
docker compose up --build
```

### El backend no refleja cambios

Podés reiniciar el servicio:

```bash
docker compose restart web
```

## 9) Acceso a la API

La API queda disponible en:

```bash
http://localhost:8000
```

Si el proyecto tiene rutas específicas, se acceden en función de la configuración de `urls.py`.

---

Si querés, después te puedo armar también un `README` más formal con badges, descripción del proyecto y endpoints documentados.
