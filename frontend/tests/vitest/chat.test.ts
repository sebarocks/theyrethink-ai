import { mount, tick, unmount } from "svelte";
import { afterEach, expect, test, vi } from "vitest";

// La API se mockea por completo: el componente se testea sin red ni backend (AGENTS.md §6).
const api = vi.hoisted(() => ({
  listThreads: vi.fn(),
  createThread: vi.fn(),
  deleteThread: vi.fn(),
  listMessages: vi.fn(),
  renameThread: vi.fn(),
  listMemory: vi.fn(),
  clearMemory: vi.fn(),
  streamMessage: vi.fn(),
}));

vi.mock("$lib/api/threads", () => ({
  listThreads: api.listThreads,
  createThread: api.createThread,
  deleteThread: api.deleteThread,
  listMessages: api.listMessages,
  renameThread: api.renameThread,
}));

vi.mock("$lib/api/memory", () => ({
  listMemory: api.listMemory,
  clearMemory: api.clearMemory,
}));

vi.mock("$lib/api/chat", () => ({
  streamMessage: api.streamMessage,
}));

import { m } from "../../src/lib/paraglide/messages.js";
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
  expect(api.streamMessage).toHaveBeenCalledWith(
    THREAD.id,
    "¿qué tal?",
    expect.any(AbortSignal),
  );
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
    expect(api.streamMessage).toHaveBeenCalledWith(
      THREAD.id,
      "hola",
      expect.any(AbortSignal),
    );
    expect(target.textContent).toContain("Hola");
  });
});

test("aborta el stream al desmontar el componente", async () => {
  api.listThreads.mockResolvedValue([THREAD]);
  api.listMessages.mockResolvedValue([]);
  let captured: AbortSignal | undefined;
  api.streamMessage.mockImplementation(
    (_id: number, _text: string, signal?: AbortSignal) => {
      captured = signal;
      return (async function* () {
        await new Promise<never>((_resolve, reject) => {
          signal?.addEventListener(
            "abort",
            () => reject(new DOMException("aborted", "AbortError")),
          );
        });
        yield { type: "done" as const };
      })();
    },
  );

  render();
  await vi.waitFor(() => expect(api.listThreads).toHaveBeenCalled());
  await typeAndSend("hola");
  await vi.waitFor(() => expect(captured).toBeDefined());

  unmount(instance!);
  instance = undefined;

  expect(captured!.aborted).toBe(true);
});

test("no escribe tokens del hilo anterior tras cambiar de hilo", async () => {
  const other = { ...THREAD, id: 8, title: "Otro hilo" };
  api.listThreads.mockResolvedValue([THREAD, other]);
  api.listMessages.mockImplementation((id: number) =>
    id === other.id ? [{ role: "user", text: "en B" }] : []
  );
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  api.streamMessage.mockImplementation(async function* () {
    yield { type: "chunk", text: "A1" };
    await gate;
    yield { type: "chunk", text: "A2" };
  });

  render();
  await vi.waitFor(() => expect(api.listThreads).toHaveBeenCalled());
  await typeAndSend("hola");
  await vi.waitFor(() => expect(target.textContent).toContain("A1"));

  const otherButton = [...target.querySelectorAll("button")].find(
    (button) => button.textContent?.trim() === "Otro hilo",
  );
  expect(otherButton).toBeDefined();
  otherButton!.click();
  await vi.waitFor(() => expect(target.textContent).toContain("en B"));

  release();
  await tick();
  await tick();

  expect(target.textContent).not.toContain("A2");
});

function findButton(label: string): HTMLButtonElement | undefined {
  return [...target.querySelectorAll("button")].find(
    (button) => button.textContent?.trim() === label,
  ) as HTMLButtonElement | undefined;
}

test("muestra y olvida la memoria del agente", async () => {
  api.listThreads.mockResolvedValue([THREAD]);
  api.listMessages.mockResolvedValue([]);
  api.listMemory.mockResolvedValue([{
    content: "vive en Santiago",
    category: null,
  }]);
  api.clearMemory.mockResolvedValue(undefined);

  render();
  await vi.waitFor(() => expect(api.listThreads).toHaveBeenCalled());

  findButton(m.chat_tabMemory())?.click();
  await vi.waitFor(() =>
    expect(target.textContent).toContain("vive en Santiago")
  );
  expect(api.listMemory).toHaveBeenCalledWith(1);

  findButton(m.chat_clearMemory())?.click();
  await tick();
  findButton(m.common_confirm())?.click();

  await vi.waitFor(() => expect(api.clearMemory).toHaveBeenCalledWith(1));
  await vi.waitFor(() =>
    expect(target.textContent).toContain(m.chat_memoryCleared())
  );
  expect(target.textContent).toContain(m.chat_noLearnedFacts());
});

test("renombra un hilo desde la lista", async () => {
  api.listThreads.mockResolvedValue([THREAD]);
  api.listMessages.mockResolvedValue([]);
  api.renameThread.mockResolvedValue({ ...THREAD, title: "Nuevo título" });

  render();
  await vi.waitFor(() => expect(api.listThreads).toHaveBeenCalled());

  const renameButton = target.querySelector(
    `button[aria-label="${m.chat_renameChat()}"]`,
  ) as HTMLButtonElement | null;
  expect(renameButton).not.toBeNull();
  renameButton!.click();
  await tick();

  const input = target.querySelector("input");
  expect(input).not.toBeNull();
  input!.value = "Nuevo título";
  const inputEvent = document.createEvent("Event");
  inputEvent.initEvent("input", true, false);
  input!.dispatchEvent(inputEvent);
  await tick();

  (target.querySelector("form") as HTMLFormElement).requestSubmit();

  await vi.waitFor(() =>
    expect(api.renameThread).toHaveBeenCalledWith(THREAD.id, "Nuevo título")
  );
});
