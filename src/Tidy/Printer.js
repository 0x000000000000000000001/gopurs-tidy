// JavaScript keeps Dodo's string buffer; its engine already supports ropes.
export const emptyBuffer = "";
export const appendText = text => buffer => buffer + text;
export const flushBuffer = buffer => buffer;
