# 0008 — Memoria por `(agente, usuario)`

- **Estado:** aceptada
- **Fecha:** 2026-09-16
- **Fuente:** propuesta §3 (A9), §5.3, §14 (D1); plan §3

## Contexto
Los hechos que extrae el agente son sobre la persona que conversa. Si la memoria se guarda por agente, dos usuarios distintos del mismo agente comparten recuerdos y se filtran datos entre cuentas.

## Decisión
La memoria se aísla por namespace **`("agent", agent_id, "user", user_id)`**, donde `user_id` referencia la tabla `users` (D6). Cada agente consulta e inyecta su memoria **siempre**: no existe interruptor de configuración.

## Alternativas consideradas
- **Memoria compartida por agente:** descartada; mezcla hechos de usuarios distintos y escala peor.
- **Hechos globales del agente**, `("agent", agent_id, "shared")`: fuera del alcance inicial, se evalúa en Fase 7.

## Consecuencias
- Aislamiento por cuenta, con test explícito entre dos `users` distintos.
- Contrapartida aceptada en D6: dos personas que compartan una cuenta comparten memoria.
- `load_context` consulta el Store en cada turno; la inyección y su techo se gobiernan por D7 (ADR 0013).
- Obliga a: nunca mezclar memorias entre usuarios al leer o escribir el Store.
