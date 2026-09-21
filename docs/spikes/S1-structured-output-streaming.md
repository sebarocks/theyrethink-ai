# S1 — Salida estructurada y streaming en un cliente OpenAI-compatible

- **Fecha:** 2026-09-21
- **Estado:** ✅ concluido (validado contra un proveedor real)
- **Bloquea:** Fase 2
- **Ámbito:** `langchain-openai` en `backend/`, contra un endpoint OpenAI-compatible real

## Pregunta

¿El cliente OpenAI-compatible elegido (A3 revisada, D15) soporta `with_structured_output`
**y** streaming de forma estable y concurrente?

## Configuración de referencia (recomendada, no obligatoria)

| Parámetro | Valor |
|---|---|
| Proveedor | **OpenRouter** (`https://openrouter.ai/api/v1`), API OpenAI-compatible |
| Modelo de referencia | **`openai/gpt-5.6-luna`** (recomendado) |
| Contexto | **1 050 000** tokens (`context_length` de `GET /models`) |
| Salida máxima | 128 000 tokens (`max_completion_tokens`) |
| Cliente | `langchain-openai` 1.6.2 · `langchain-core` 1.6.3 · `pydantic` 2.13.5 |

Los tres valores (`base_url`, `api_key`, `model`) llegan por **variables de entorno** (D15);
el código no fija proveedor ni modelo. La clave **no** se registra aquí.

## Política de modelos: recomendado, no obligatorio

- **`openai/gpt-5.6-luna` es el modelo recomendado** porque pasó todas las condiciones
  (veredicto `COMPLETO`). **No es un pin**: D15 deja proveedor y modelo por entorno.
- **Cualquier modelo OpenAI-compatible está permitido.** Se valida con el harness
  `backend/scripts/spike_s1.py` antes de adoptarlo; el catálogo de modelos soportados se
  irá definiendo más adelante, sin imponer límites hoy.
- **Degradación esperada** si un modelo no cumple todo, en este orden:
  1. `json_schema` (esquema impuesto, preferido);
  2. `function_calling` (tool calling; D15 lo acepta como equivalente);
  3. `json_mode` + validación Pydantic propia (plan B; **logro parcial**);
  4. si nada de lo anterior es fiable, el seam debe **fallar con un error claro**.
- El harness emite un veredicto graduado: `COMPLETO` / `CUMPLE` / `PARCIAL` / `NO CUMPLE`.

## Lo que se ejecutó

`backend/scripts/spike_s1.py` (harness agnóstico de proveedor, lee `app.config.Settings`):
streaming del chat, `with_structured_output` por los tres métodos (extractor **sin**
streaming), fiabilidad, concurrencia, `system` en medio del array, caché de prefijo y
`GET /models`.

## Resultados (modelo de referencia)

| Comprobación | Resultado |
|---|---|
| Streaming del chat (`astream`) | ✅ 28 chunks, primer token ~1,4 s |
| `with_structured_output(method="json_schema")` | ✅ **fiabilidad 5/5** |
| `with_structured_output(method="function_calling")` | ✅ **fiabilidad 5/5** |
| `with_structured_output(method="json_mode")` | ❌ no respeta el esquema (`OutputParserException`) |
| Concurrencia (chat en streaming + 4 extracciones) | ✅ 0 fallos |
| `system` en medio del array (requisito D7) | ✅ aceptado y respetado |
| Caché de prefijo (requisito D7) | ✅ `usage_metadata.input_token_details.cache_read` > 0 |
| Contexto | 1 050 000 → techo `0.4 ×` ≈ **420 000** tokens |

## Conclusiones

1. **La costura funciona.** `ChatOpenAI` con `base_url` propaga la configuración y cubre
   streaming y salida estructurada. El proveedor es intercambiable por entorno (D15).
2. **`json_object` ≠ `json_schema`.** `json_object` solo garantiza JSON válido; la forma la
   decide el modelo. `json_schema` **impone** el esquema. D15 pide «salida estructurada o
   *tool calling*», así que se cumple con `json_schema` **o** `function_calling`, no con
   `json_object` a secas.
3. **Método preferido: `json_schema`** (único que garantiza el esquema). `function_calling`
   es equivalente funcional y *fallback*. `json_mode` solo cuenta como **logro parcial**
   (exige plan B con validación propia).
4. **El extractor va separado del chat y sin streaming** (`temperature=0`). La salida
   estructurada necesita la respuesta completa para parsear y validar; además, la ruta
   *streaming + structured* de `langchain-openai` 1.6.2 emite un warning de serialización de
   Pydantic (`chunk.model_dump()` sin `warnings=False` en `_astream`), que con
   `streaming=False` no se recorre.
5. **D7 es viable tal como está diseñado:** se puede inyectar `system` (memoria) antes del
   mensaje nuevo, y la caché de prefijo se reporta en `usage_metadata`, así que la métrica de
   tokens cacheados/inyectados es observable sin instrumentación extra.
6. **Techo de inyección:** `0.4 × contexto`, derivado en runtime del contexto real del modelo
   (no un número fijo).

## Consecuencias para la Fase 2

- `agent/llm.py`: fábrica agnóstica; chat con `streaming=True`; extractor con `temperature=0`,
  `streaming=False` y `method="json_schema"` (con `function_calling` como *fallback*).
- Los errores del proveedor se tipan y se propagan con mensaje claro: si un modelo no cumple
  una condición, el fallo debe ser explícito, no silencioso.
- La métrica de caché y de tokens inyectados se lee de `usage_metadata`.
- Para adoptar otro modelo, basta re-ejecutar `scripts/spike_s1.py --model <modelo>`.

## Fuera de alcance de S1

- **Calidad multilingüe** (es, en, fr, pt, ko, zh) y **costo**: son condiciones de D15 que
  este spike no mide; se evalúan aparte.
