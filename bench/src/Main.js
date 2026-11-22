import fs from "node:fs";

export const fixture = () => fs.readFileSync("fixture.purs", "utf8");
export const log = (message) => () => console.log(message);
