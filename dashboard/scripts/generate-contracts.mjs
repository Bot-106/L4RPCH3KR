import { compileFromFile } from "json-schema-to-typescript";
import { mkdir, readdir, writeFile } from "node:fs/promises";
import path from "node:path";

const root = process.cwd();
const schemaDir = path.resolve(root, "../contracts/schemas");
const outDir = path.resolve(root, "src/contracts/generated");

await mkdir(outDir, { recursive: true });
const files = (await readdir(schemaDir)).filter((file) => file.endsWith(".schema.json"));

for (const file of files) {
  const ts = await compileFromFile(path.join(schemaDir, file), { bannerComment: "" });
  await writeFile(path.join(outDir, file.replace(".schema.json", ".ts")), ts);
}
