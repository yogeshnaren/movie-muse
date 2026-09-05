import { assertCommandIsNotCanonSave } from "../commands";
import { reduceSession, initialSession } from "../session";
import type { EditorCommand } from "../types";

describe("command protocol", () => {
  it("rejects editor JSON posed as a command", () => {
    const payload = {
      type: "update_text",
      blockId: "blk_action",
      text: "no",
      format: "movie-muse.editor.projection.v1",
      nodes: [],
    };
    expect(() => assertCommandIsNotCanonSave(payload as unknown as EditorCommand)).toThrow(
      /cannot be saved as ScreenplayDocument canon/
    );
  });

  it("applies typed update commands to the local snapshot", () => {
    const next = reduceSession(initialSession(), {
      type: "update_text",
      blockId: "blk_action",
      text: "Ada writes.",
    });
    expect(next.document.blocks[1].text).toBe("Ada writes.");
    expect(next.document.revisionId).not.toBe("rev_local_0");
  });

  it("inserts a character block on Tab from action", () => {
    const next = reduceSession(initialSession(), {
      type: "transition",
      blockId: "blk_action",
      key: "Tab",
    });
    expect(next.document.blocks[2].kind).toBe("character");
  });
});
