import { mount, tick, unmount } from "svelte";
import { afterEach, expect, test, vi } from "vitest";

// La API se mockea por completo: el componente se testea sin red ni backend (AGENTS.md §6).
const api = vi.hoisted(() => ({
  listThreads: vi.fn(),
  createThread: vi.fn(),
  deleteThread: vi.fn(),
  listMessages: vi.fn(),
  streamMessage: vi.fn(),
}));

vi.mock("$lib/api/threads", () => ({
  listThreads: api.listThreads,
  createThread: api.createThread,
  deleteThread: api.deleteThread,
  listMessages: api.listMessages,
}));

vi.mock("$lib/api/chat", () => ({
  streamMessage: api.streamMessage,
}));

import Chat from "../../src/lib/chat/Chat.svelte";

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

let target: HTMLElement;
let instance: ReturnType<typeof mount> | undefined;

function render() {
  target = document.createElement("div");
  document.body.append(target);
  instance = mount(Chat, {
    target,
    props: { agentId: 1, agentName: "Rethink" },
  });
}

async function typeAndSend(text: string) {
  const textarea = target.querySelector("textarea");
  const form = target.querySelector("form");
  if (textarea === null || form === null) {
    throw new Error("falta el Composer");
  }
  textarea.value = text;
  // El evento se crea con `document.createEvent` (realm de jsdom) y no con el `Event`
  // global del worker de Vitest: jsdom rechaza eventos de otro realm con
  // «parameter 1 is not of type 'Event'».
  const input = document.createEvent("Event");
  input.initEvent("input", true, false);
  textarea.dispatchEvent(input);
  await tick();
  // `requestSubmit()` dispara el submit ya registrado por Svelte; construir el evento a
  // mano bajo jsdom termina en el mismo error de realm.
  (form as HTMLFormElement).requestSubmit();
  await tick();
}

afterEach(() => {
  if (instance !== undefined) unmount(instance);
  target?.remove();
  instance = undefined;
  vi.clearAllMocks();
});

test("carga el historial y hace streaming de los tokens", async () => {
  api.listThreads.mockResolvedValue([THREAD]);
  api.listMessages.mockResolvedValue([{ role: "user", text: "hola" }]);
  api.streamMessage.mockImplementation(async function* () {
    yield { type: "chunk", text: "Ho" };
    yield { type: "chunk", text: "la" };
    yield { type: "done" };
  });

  render();

  await vi.waitFor(() => {
    expect(api.listMessages).toHaveBeenCalledWith(THREAD.id);
    expect(target.textContent).toContain("hola");
  });

  await typeAndSend("¿qué tal?");

  await vi.waitFor(() => {
    expect(target.textContent).toContain("¿qué tal?");
    expect(target.textContent).toContain("Hola");
  });
  expect(api.streamMessage).toHaveBeenCalledWith(THREAD.id, "¿qué tal?");
});

test("muestra el detalle de un evento de error sin romper el flujo", async () => {
  api.listThreads.mockResolvedValue([THREAD]);
  api.listMessages.mockResolvedValue([]);
  api.streamMessage.mockImplementation(async function* () {
    yield { type: "chunk", text: "par" };
    yield { type: "error", code: "provider_error", detail: "proveedor caído" };
  });

  render();
  await vi.waitFor(() => expect(api.listThreads).toHaveBeenCalled());

  await typeAndSend("hola");

  await vi.waitFor(() => {
    expect(target.textContent).toContain("proveedor caído");
  });
});

test("crea un hilo al enviar si todavía no hay ninguno", async () => {
  api.listThreads.mockResolvedValue([]);
  api.createThread.mockResolvedValue(THREAD);
  api.listMessages.mockResolvedValue([]);
  api.streamMessage.mockImplementation(async function* () {
    yield { type: "chunk", text: "Hola" };
  });

  render();
  await vi.waitFor(() => expect(api.listThreads).toHaveBeenCalled());

  await typeAndSend("hola");

  await vi.waitFor(() => {
    expect(api.createThread).toHaveBeenCalledWith(1);
    expect(api.streamMessage).toHaveBeenCalledWith(THREAD.id, "hola");
    expect(target.textContent).toContain("Hola");
  });
});
