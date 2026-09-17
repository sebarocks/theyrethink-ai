# 0006 — Una costura fina, no un hexágono

- **Estado:** aceptada
- **Fecha:** 2026-09-16
- **Fuente:** propuesta §3 (A8), §5.1, §15; plan §1 (DoD 3), §2 (S5)

## Contexto
El acoplamiento del proyecto actual (lógica del agente entrelazada con SQL y con HTTP) hay que cortarlo, pero sin pagar la ceremonia de una arquitectura de puertos y adaptadores que no aporta al objetivo de este rewrite.

## Decisión
Una sola costura: **`agent/service.py`**, que es la API pública del núcleo y devuelve **DTOs de dominio** (nunca `BaseMessage` ni tipos de la librería). `langgraph` y `langchain` se importan **solo** dentro de `backend/app/agent/`.

## Alternativas consideradas
- **Puertos y adaptadores formales:** descartado; el objetivo es menos código, y el grafo queda igualmente encerrado tras una función de servicio.

## Consecuencias
- Cambiar de librería, o de proveedor LLM (D15), toca este módulo y no los routers.
- `import-linter` verifica el aislamiento en CI: contrato definido en Fase 0 y activo desde la Fase 2 (spike S5). Si falla, se corrige el import, no se silencia.
- El núcleo se testea sin I/O real (`FakeLLM`, `InMemorySaver`, `InMemoryStore`, cola falsa).
- Cuesta disciplina: no hay puertos que documenten los casos de uso, así que la barrera real es el contrato de imports más la revisión.
