import { mount, unmount } from "svelte";
import { afterEach, expect, test } from "vitest";

import Markdown from "../../src/lib/chat/Markdown.svelte";

let target: HTMLElement;
let instance: ReturnType<typeof mount> | undefined;

function render(text: string) {
  target = document.createElement("div");
  document.body.append(target);
  instance = mount(Markdown, { target, props: { text } });
}

afterEach(() => {
  if (instance !== undefined) unmount(instance);
  target?.remove();
  instance = undefined;
});

test("renderiza bloques e inline como elementos", () => {
  render("# Hola\n\n- uno\n- dos\n\n**fuerte** y `code`");

  expect(target.querySelector("p")?.textContent).toContain("Hola");
  expect([...target.querySelectorAll("li")].map((item) => item.textContent))
    .toEqual([
      "uno",
      "dos",
    ]);
  expect(target.querySelector("strong")?.textContent).toBe("fuerte");
  expect(target.querySelector("code")?.textContent).toBe("code");
});

test("no inyecta HTML del modelo", () => {
  render("<script>alert(1)</script><img src=x onerror=alert(1)>");

  expect(target.querySelector("script")).toBeNull();
  expect(target.querySelector("img")).toBeNull();
  // El marcado queda como texto visible, no como elemento.
  expect(target.textContent).toContain("<script>");
});

test("solo enlaza esquemas permitidos", () => {
  render("[x](javascript:alert(1)) [ok](https://example.test)");

  const links = [...target.querySelectorAll("a")];
  expect(links.map((link) => link.getAttribute("href"))).toEqual([
    "https://example.test",
  ]);
});
