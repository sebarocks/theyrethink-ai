# 0004 — Cliente LLM OpenAI-compatible con proveedor por configuración

- **Estado:** aceptada — **reemplaza la elección original de A3** (`langchain-deepseek`)
- **Fecha:** 2026-09-16
- **Fuente:** propuesta §3 (A3 revisada), §5.4, §14 (D15); plan §2 (S1), §5 Fase 2

## Contexto
La elección original de A3 se hizo cuando 128K de contexto bastaba y el precio mandaba. Hoy D7 asume contextos de 1M y el código quedaría atado a un proveedor concreto, sin camino para cambiar de modelo.

## Decisión
Un cliente **OpenAI-compatible** (`langchain-openai` / `init_chat_model`) con proveedor y modelo por **variables de entorno** (`base_url`, `api_key`, `model`), expuesto como única puerta en `agent/llm.py`.

## Alternativas consideradas
- **`langchain-deepseek` (A3 original):** descartado como elección vigente; un solo camino de código para cualquier proveedor reduce el acoplamiento, y el modelo deja de fijarse en el código.

## Condiciones que debe cumplir el modelo elegido (D15)
- Contexto amplio (1M deseable; el techo de memoria es `0.4 × contexto`), **streaming** de tokens y salida estructurada o *tool calling* para el extractor.
- **Caché de prompt por prefijo**, con descuento relevante en *cache hit*.
- Poder insertar mensajes de rol `system` en medio del array (requisito de la inyección al final, D7) o una alternativa equivalente.
- Calidad en los 6 idiomas (es, en, fr, pt, ko, zh) y concurrencia para chat en streaming + extracción en background.

## Consecuencias
- Cambiar de proveedor toca solo `agent/llm.py`; el techo de inyección se deriva del contexto real en runtime.
- El seam absorbe timeouts, retries y la taxonomía de errores del proveedor portada del proyecto actual.
- Cuesta validar cada condición en el spike S1; si `with_structured_output` falla, el plan B es JSON mode + validación Pydantic propia.
- Los parámetros específicos del proveedor anterior que se pierdan quedan absorbidos por el seam (§8).
