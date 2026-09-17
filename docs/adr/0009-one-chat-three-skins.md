# 0009 — Un solo `<Chat>` y tres skins

- **Estado:** aceptada
- **Fecha:** 2026-09-16
- **Fuente:** propuesta §3 (A10), §9.1, §14 (D3); plan §5 Fase 4

## Contexto
El proyecto actual duplica el mismo chat en 3 plantillas + JS por canal, y esa duplicación es uno de los focos de mantenimiento. Los tres canales comparten comportamiento y difieren solo en la cáscara visual.

## Decisión
Los tres canales (Web, WhatsApp, Telegram) son **siempre skins** de un único componente `<Chat>`. Prohibido ramificar comportamiento por canal: los slots y props de variante existen únicamente para personalización estética.

## Alternativas consideradas
- **Comportamiento divergente por canal:** descartado; implicaba lógica duplicada y deriva entre canales.

## Consecuencias
- Las rutas `/web/[agent]`, `/whatsapp/[agent]` y `/telegram/[agent]` montan el mismo `<Chat>` con distinto skin.
- Telegram expone `/start`, `/bases` y `/memoria` como **atajos**, no como lógica propia.
- Cuesta: WhatsApp y Telegram son vistas del mismo frontend autenticado, no integraciones reales de mensajería (coherente con D6). Si algún día hace falta comportamiento por canal, esta decisión se revisa con un ADR nuevo.
