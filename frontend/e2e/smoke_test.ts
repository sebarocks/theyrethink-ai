/// <reference lib="deno.ns" />
// Smoke E2E del frontend bajo Deno + Playwright (spike S6): la API se intercepta con
// `page.route`, así que el test es hermético — no necesita backend, Postgres ni proveedor LLM.
import { assert } from "@std/assert";
import { chromium, type Route } from "playwright";

const PORT = 4173;
const BASE_URL = `http://127.0.0.1:${PORT}`;
const BUILD_DIR = new URL("../build/", import.meta.url);

const CONTENT_TYPES: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
};

function contentType(path: string): string {
  const dot = path.lastIndexOf(".");
  return CONTENT_TYPES[dot === -1 ? "" : path.slice(dot)] ??
    "application/octet-stream";
}

/** Sirve `build/` con el fallback de SPA de `adapter-static` (`200.html`). */
async function startServer(): Promise<Deno.HttpServer> {
  const fallback = await Deno.readFile(new URL("200.html", BUILD_DIR)).catch(
    () => null,
  );
  if (fallback === null) {
    throw new Error(
      "falta `frontend/build/`; ejecuta `deno task build` antes del E2E",
    );
  }

  return Deno.serve({
    port: PORT,
    hostname: "127.0.0.1",
    onListen: () => {},
  }, async (request) => {
    const pathname = decodeURIComponent(new URL(request.url).pathname);
    if (request.method !== "GET") {
      return new Response("method not allowed", { status: 405 });
    }
    const file = pathname === "/" ? "index.html" : pathname.slice(1);
    if (file.includes("..")) return new Response("bad path", { status: 400 });
    try {
      const data = await Deno.readFile(new URL(file, BUILD_DIR));
      return new Response(data, {
        headers: { "content-type": contentType(file) },
      });
    } catch {
      return new Response(fallback, {
        headers: { "content-type": CONTENT_TYPES[".html"] },
      });
    }
  });
}

const USER = {
  id: 1,
  username: "admin",
  email: "admin@example.com",
  role: "admin",
};

const AGENT = {
  id: 1,
  name: "Rethink",
  profile: "",
  role_key: null,
  custom_identity: null,
  avatar_url: null,
};

const THREAD = {
  id: 7,
  agent_id: 1,
  user_id: 1,
  title: "Nueva conversación",
  message_count: 0,
  last_preview: "",
  last_consolidated_at: null,
  created_at: "2026-09-28T00:00:00Z",
  updated_at: "2026-09-28T00:00:00Z",
};

const ERROR_BODY = JSON.stringify({
  error: "unauthorized",
  code: "unauthorized",
  detail: "no session",
});

function json(route: Route, body: unknown): Promise<void> {
  return route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

/** API falsa: la sesión nace anónima y solo existe tras `POST /auth/login`. */
async function mockApi(page: import("playwright").Page): Promise<void> {
  let loggedIn = false;
  let thread = { ...THREAD };

  await page.route("**/api/v1/**", (route) => {
    const request = route.request();
    const method = request.method();
    const path = new URL(request.url()).pathname;

    if (path === "/api/v1/auth/login" && method === "POST") {
      loggedIn = true;
      return json(route, USER);
    }
    if (path === "/api/v1/auth/logout" && method === "POST") {
      loggedIn = false;
      return route.fulfill({ status: 204 });
    }
    if (path === "/api/v1/auth/me") {
      return loggedIn ? json(route, USER) : route.fulfill({
        status: 401,
        contentType: "application/json",
        body: ERROR_BODY,
      });
    }
    if (path === "/api/v1/agents" && method === "GET") {
      return json(route, [AGENT]);
    }
    if (path === "/api/v1/agents/1" && method === "GET") {
      return json(route, AGENT);
    }
    if (path === "/api/v1/agents/1/memory") {
      if (method === "DELETE") return route.fulfill({ status: 204 });
      return json(route, {
        facts: [{ content: "vive en Santiago", category: null }],
      });
    }
    if (path === "/api/v1/threads" && method === "GET") {
      return json(route, [thread]);
    }
    if (path === "/api/v1/threads" && method === "POST") {
      return json(route, thread);
    }
    if (path === "/api/v1/threads/7" && method === "PATCH") {
      const body = request.postDataJSON() as { title?: string };
      thread = { ...thread, title: body.title ?? thread.title };
      return json(route, thread);
    }
    if (/^\/api\/v1\/threads\/\d+\/messages$/.test(path)) {
      if (method === "GET") return json(route, []);
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: [
          'event: chunk\ndata: {"text":"Hola"}\n\n',
          'event: chunk\ndata: {"text":" mundo"}\n\n',
          "event: done\ndata: {}\n\n",
        ].join(""),
      });
    }
    return route.fulfill({ status: 404, body: ERROR_BODY });
  });
}

Deno.test("smoke: login → agentes → chat con streaming → skins → logout", async () => {
  const server = await startServer();
  const browser = await chromium.launch();
  // El runner de CI trae un navegador en `en-US` (en local suele ser `es`). Se fija el idioma
  // del *navegador* a `en-US` para no depender de la máquina, y el de la *app* en el script de
  // abajo, para que las aserciones de texto sean deterministas.
  const page = await browser.newPage({ locale: "en-US" });
  // La app resuelve el idioma con `localStorage preferredLanguage baseLocale`; se fija la
  // locale base (`es`) antes de cargar nada para que los textos no dependan del navegador.
  await page.addInitScript('localStorage.setItem("PARAGLIDE_LOCALE", "es");');
  try {
    await mockApi(page);

    // Sin sesión la guarda lleva a /login.
    await page.goto(`${BASE_URL}/`);
    await page.locator('input[autocomplete="username"]').waitFor();

    await page.locator('input[autocomplete="username"]').fill("admin");
    await page.locator('input[type="password"]').fill("secret");
    await page.locator('form button[type="submit"]').click();

    // Home con el catálogo de agentes.
    await page.locator('a[href="/web/1"]').waitFor();
    assert(
      (await page.getByText(AGENT.name).count()) > 0,
      "el agente no aparece en la home",
    );

    // Skin web: un turno completo con streaming SSE.
    await page.locator('a[href="/web/1"]').click();
    await page.locator("textarea").waitFor();
    await page.locator("textarea").fill("hola");
    await page.locator('form button[type="submit"]').click();
    await page.getByText("Hola mundo").waitFor();
    assert(
      (await page.getByText("hola").count()) > 0,
      "falta el mensaje del usuario",
    );

    // Memoria visible y olvidable (D10).
    await page.getByRole("button", { name: "Memoria", exact: true }).click();
    await page.getByText("vive en Santiago").waitFor();
    await page.getByRole("button", { name: "Limpiar memoria" }).click();
    await page.getByRole("button", { name: "Confirmar" }).click();
    await page.getByText("Memoria eliminada correctamente").waitFor();

    // Renombrado de hilo en línea.
    await page.locator('button[aria-label="Renombrar Conversación"]').first()
      .click();
    await page.locator('input[aria-label="Renombrar Conversación"]').fill(
      "Charla renombrada",
    );
    await page.locator('input[aria-label="Renombrar Conversación"]').press(
      "Enter",
    );
    await page.getByText("Charla renombrada").waitFor();

    // Las otras dos skins montan el mismo `<Chat>`; Telegram añade sus atajos.
    for (const skin of ["whatsapp", "telegram"]) {
      await page.goto(`${BASE_URL}/${skin}/1`);
      await page.locator("textarea").waitFor();
      assert(
        (await page.getByText(AGENT.name).count()) > 0,
        `la skin ${skin} no muestra el agente`,
      );
    }
    await page.getByRole("button", { name: "/memoria" }).waitFor();

    // Logout: vuelve a /login y la sesión queda vacía.
    await page.goto(`${BASE_URL}/`);
    await page.getByRole("button", { name: /log out|cerrar sesión/i }).click();
    await page.waitForURL("**/login");
    await page.locator('input[autocomplete="username"]').waitFor();
  } finally {
    await browser.close();
    await server.shutdown();
  }
});
