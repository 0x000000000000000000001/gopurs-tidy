import { readFileSync, writeFileSync, writeSync } from "node:fs";
import { formatOnce, consume } from "./output/Main/index.js";

const [mode, input, destination] = process.argv.slice(2);
const source = readFileSync(input, "utf8");
if (mode === "verify") {
  const text = formatOnce(source);
  if (!text.isWellFormed()) throw new Error("Verification requires well-formed Unicode");
  const bytes = Buffer.from(text, "utf8");
  writeFileSync(destination, bytes);
  console.log(JSON.stringify({ bytes: bytes.length, checksum: consume(text) }));
} else if (mode === "allocations") {
  // GC traces estimate V8 heap allocations; external Buffer payloads are
  // accounted separately from the verified output length in measure.py.
  global.gc();
  writeSync(1, "\nALLOC_BEGIN\n");
  let checksum = 0;
  for (let i = 0; i < 10; i++) checksum += consume(formatOnce(source));
  global.gc();
  writeSync(1, "\nALLOC_END\n");
  console.log(JSON.stringify({ checksum }));
} else {
  throw new Error("Expected verify or allocations mode");
}
