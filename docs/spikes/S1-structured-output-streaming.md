# S1 — Salida estructurada y streaming en un cliente OpenAI-compatible

- **Fecha:** 2026-09-16
- **Estado:** 🟡 parcial — **falta la validación contra un proveedor real** (requiere credenciales)
- **Bloquea:** Fase 2
- **Ámbito:** `langchain-openai` instalado en `backend/`

## Pregunta

¿El cliente OpenAI-compatible elegido (A3 revisada, D15) soporta `with_structured_output`
**y** streaming de forma estable y concurrente?

## Lo que se ejecutó

Comprobación de la superficie de la librería: se construyó un `ChatOpenAI` con `base_url` y
`api_key` de prueba (sin llamada de red) y se inspeccionaron sus capacidades. También se
verificó que `init_chat_model` acepta una cadena `"provider:model"` junto a `base_url`.

## Resultados (parte verificada)

| Comprobación | Resultado |
|---|---|
| `ChatOpenAI` expone `with_structured_output` | ✅ |
| `ChatOpenAI` expone `astream` (streaming asíncrono) | ✅ |
| `ChatOpenAI` expone `bind_tools` (vía alternativa a la salida estructurada) | ✅ |
| `init_chat_model("openai:x", base_url=..., api_key=...)` | ✅ devuelve `ChatOpenAI` |

Es decir: **la superficie que necesita la Fase 2 existe y `base_url` se propaga**, que es la
condición para que el proveedor sea configurable por entorno (D15).

## Lo que NO se pudo verificar

Todo lo que depende del proveedor real queda pendiente, porque requiere credenciales:

1. Que el modelo elegido respete de verdad el **esquema** de `ExtractedMemories` (los modelos
   pequeños suelen degradar el JSON).
2. Si conviene `method="json_schema"`, `"function_calling"` o `"json_mode"` según el
   proveedor; **no todos soportan los tres**.
3. Si **streaming y salida estructurada se pueden usar en la misma llamada**, o si hay que
   separar el modelo del extractor (temperatura 0, sin streaming) del modelo del chat.
4. Los **límites de concurrencia**: chat en streaming + extracción en background a la vez.
5. El comportamiento de la **caché de prompt** (S1 no lo cubre; es la métrica de la Fase 2).

## Recomendación

- Diseñar el extractor como una llamada **separada y sin streaming** (temperatura 0). Es más
  simple, más barato y elimina la pregunta 3 de raíz.
- Cuando D15 fije proveedor y modelo, cerrar este spike con una llamada real que valide el
  esquema y mida la tasa de JSON inválido. **Es un requisito de entrada de la Fase 2.**
- Plan B si la salida estructurada del proveedor no es fiable: `json_mode` + validación
  Pydantic propia, que ya está prevista en el plan §2.