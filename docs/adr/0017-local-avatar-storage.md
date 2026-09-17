# 0017 — Avatares en almacenamiento local

- **Estado:** aceptada
- **Fecha:** 2026-09-16
- **Fuente:** propuesta §11, §14 (D12); plan §5 Fases 3 y 6

## Contexto
El proyecto actual sirve los avatares subidos desde `static/` y admite `.svg` (`app.py:82`), lo que expone contenido subido por el usuario desde el mismo origen del frontend. Hay que decidir dónde viven los archivos y cómo se sirven.

## Decisión
Almacenamiento **local**, en un directorio **fuera** de lo servido como estático (volumen propio), servido por un endpoint con `Content-Disposition` y **sin SVG**.

## Alternativas consideradas
- **Servir desde `static/`:** descartado; entrega el archivo tal cual, con el tipo declarado por quien lo sube.
- **S3 u objeto externo:** descartado; suma superficie operativa y un proveedor más, sin necesidad medida hoy.

## Consecuencias
- La subida exige límite de tamaño y validación de tipo (Fase 3); límites y volumen se cierran en Fase 6.
- Sin SVG se evita servir contenido activo desde el mismo origen de la sesión.
- Cuesta: el volumen se respalda por separado de la BD, y con varios nodos hace falta un volumen compartido.
