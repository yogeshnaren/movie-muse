import type { EditorCommand } from "./types";

const CANON_KEYS = new Set(["format", "nodes", "editorJson", "projection"]);

/** Editor JSON is a projection. It must never be submitted as document canon. */
export function assertCommandIsNotCanonSave(command: EditorCommand): EditorCommand {
  const record = command as unknown as Record<string, unknown>;
  if (record.format === "movie-muse.editor.projection.v1" || "nodes" in record) {
    throw new Error("editor projection cannot be saved as ScreenplayDocument canon");
  }
  for (const key of CANON_KEYS) {
    if (key in record && key !== "type") {
      throw new Error("unknown payload is not a typed document command");
    }
  }
  return command;
}

export function commandLabel(command: EditorCommand): string {
  switch (command.type) {
    case "update_text":
      return `update ${command.blockId}`;
    case "transition":
      return `${command.key} ${command.blockId}`;
    case "set_mode":
      return `mode ${command.mode}`;
    case "set_airplane":
      return command.enabled ? "airplane on" : "airplane off";
    default:
      return command.type;
  }
}
