# 0026 — Límite de peticiones por ventana fija en Postgres

- **Estado:** aceptada
- **Fecha:** 2026-10-02
- **Fuente:** propuesta §14 (D23, D14); ADR `0013`, `0022`

## Contexto

La propuesta §11 pide limitar intentos en `/login`; el registro público (D13) añade `/register`
y el chat consume el proveedor LLM, que es el recurso más caro del sistema. Un límite solo en
memoria del proceso es inútil con varios workers (D22): cada proceso contaría por su cuenta y el
límite efectivo se multiplicaría por `WEB_CONCURRENCY`.

La decisión D14 ya descartó añadir Redis como servicio extra. La cola de consolidación vive en
Postgres; la infraestructura del sistema es **una sola pieza** y conviene mantenerlo así.

## Decisión

Límite de **ventana fija contada en Postgres**, con *upsert* atómico:

```sql
INSERT INTO rate_limit_hits (scope, key, window_start, count)
VALUES (:scope, :key, :window_start, 1)
ON CONFLICT (scope, key, window_start) DO UPDATE SET count = rate_limit_hits.count + 1
RETURNING count
```

- **Clave (`key`):** la identidad del usuario autenticado cuando la hay; si no, la IP del
  cliente (`request.client.host`). No se confía en `X-Forwarded-For` salvo que el proxy esté
  delante y configurado: por defecto no se lee.
- **Alcances (`scope`):** `auth` para `/auth/login` y `/auth/register` (por IP) y `chat` para el
  envío de mensajes (por usuario). Límites y ventanas configurables por entorno.
- **Respuesta:** al superar el límite, `429` con el envelope estable `{error, code, detail}`.
- **Purga perezosa:** las ventanas vencidas se borran de forma oportunista al contar, sin un
  proceso de limpieza aparte.
- **Aplicación:** dependencia de FastAPI por endpoint, para que el límite sea explícito y
  testeable (y no un middleware global que afecte a healthchecks).

La migración `0005` crea la tabla.

## Alternativas consideradas

- **Memoria del proceso (`slowapi` o equivalente).** Simple, pero con N workers el límite se
  multiplica por N y no protege de verdad. Descartada por D22.
- **Redis.** Es el estándar para esto, pero añade un servicio que operar, respaldar y vigilar
  solo para un contador; contradice el criterio de D14. Descartada.
- **Token bucket en Postgres (suaviza ráfagas).** Más fiel, pero más estado y más escrituras por
  lectura; la ventana fija cubre el objetivo (frenar fuerza bruta y abuso) con menos superficie.
  Descartada de momento.
- **Limitarlo en el proxy.** Válido como primera línea, pero deja el backend desprotegido si se
  despliega sin proxy y no distingue por usuario. Se considera complemento, no sustituto.

## Consecuencias

- El límite es exacto entre workers sin infraestructura nueva.
- Cada petición limitada paga una escritura; el coste es despreciable frente al login (Argon2) o
  a una llamada al LLM.
- La tabla de límites es **operativa**, no de dominio: no guarda conversación ni memoria, así que
  no roza AGENTS.md §3.3.
- Un atacante distribuido con muchas IPs sigue pudiendo repartir intentos; el límite por IP es
  mitigación, no una defensa completa (se anota en el runbook).
