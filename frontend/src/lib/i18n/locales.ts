/** Idiomas soportados (AGENTS.md §3.7). Fuente única para el test de paridad y el port. */
export const LOCALES = ["es", "en", "fr", "pt", "ko", "zh"] as const;

export type Locale = (typeof LOCALES)[number];
