const command = new Deno.Command("deno", {
  args: [
    "run",
    "-A",
    "npm:openapi-typescript",
    "../docs/openapi.json",
    "-o",
    "src/lib/api/generated.ts",
  ],
  stdout: "inherit",
  stderr: "inherit",
});

const output = await command.output();
if (!output.success) {
  Deno.exit(output.code);
}
