# Software Intelligence — Backend

Backend en FastAPI para la plataforma RAG de consulta de proyectos de software.
Cubre: creación de usuarios, autenticación JWT con expiración por inactividad (20 min)
y, próximamente, la orquestación de proyectos/repositorios/consultas hacia el
[servicio RAG](https://ragapi-production-acb3.up.railway.app/docs).

## Stack
- FastAPI + Uvicorn
- MongoDB (Motor, async) — instancia externa en Railway
- JWT (python-jose) + bcrypt (passlib)
- Docker / docker-compose

## Cómo correrlo

```bash
cp .env.example .env
# edita .env: MONGO_URI real de Railway, JWT_SECRET propio, CORS_ORIGINS del frontend

docker compose up --build
```

La API queda en `http://localhost:8000` y la documentación interactiva (Swagger) en
`http://localhost:8000/docs` — ahí el equipo de frontend puede probar los endpoints
directamente sin escribir código.

## Endpoints actuales

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/v1/users` | Registrar usuario |
| GET | `/api/v1/users/me` | Perfil del usuario autenticado |
| POST | `/api/v1/auth/login` | Login → devuelve JWT |
| POST | `/api/v1/auth/logout` | Cierra la sesión activa |
| GET | `/health` | Estado del servicio |

## Notas de diseño

- La expiración por inactividad (20 min) se maneja con una colección `sessions` en Mongo
  (`last_activity` se actualiza en cada request autenticado), no solo con la expiración fija del JWT.
- El registro de usuarios está abierto por ahora (sin invitación/rol de admin). Pendiente
  definir si el alcance del proyecto requiere restringirlo.
- Pendiente: endpoints de proyectos/repositorios/ramas y el orquestador de consultas hacia el RAG.
