import fs from "node:fs";

export const fixture = () => fs.readFileSync("fixture.purs", "utf8");
export const log = (message) => () => console.log(message);

// Read every UTF-8 byte. Number keeps the sum of ten uint32 hashes exact.
export const consume = (text) => {
  const bytes = Buffer.from(text, "utf8");
  let hash = 2166136261;
  for (let i = 0; i < bytes.length; i++) {
    hash = Math.imul(hash ^ bytes[i], 16777619) >>> 0;
  }
  return hash;
};
