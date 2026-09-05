import { assertCommandIsNotCanonSave } from "./commands";
import {
  ENTER_TRANSITIONS,
  TAB_TRANSITIONS,
  type AuthorMode,
  type BlockKind,
  type BlockSnapshot,
  type DocumentSnapshot,
  type EditorCommand,
  type NoteSnapshot,
  type OutlineEntry,
  type SceneCard,
} from "./types";

export type EditorSessionState = {
  document: DocumentSnapshot;
  mode: AuthorMode;
  airplane: boolean;
  selectedBlockId: string;
  query: string;
  replacement: string;
  liveMessage: string;
  commands: EditorCommand[];
  undo: EditorCommand[];
  redo: EditorCommand[];
};

const SEED_BLOCKS: BlockSnapshot[] = [
  { id: "blk_heading", kind: "scene_heading", text: "INT. KITCHEN - DAY" },
  { id: "blk_action", kind: "action", text: "Ada studies the lock." },
  { id: "blk_character", kind: "character", text: "ADA" },
  { id: "blk_dialogue", kind: "dialogue", text: "It's not locked." },
];

export function seedDocument(): DocumentSnapshot {
  return {
    id: "doc_local",
    title: "Pilot",
    revisionId: "rev_local_0",
    blocks: SEED_BLOCKS,
    notes: [{ id: "note_seed", blockId: "blk_heading", text: "confirm kitchen" }],
  };
}

export function initialSession(): EditorSessionState {
  return {
    document: seedDocument(),
    mode: "author",
    airplane: false,
    selectedBlockId: "blk_action",
    query: "",
    replacement: "",
    liveMessage: "Ready.",
    commands: [],
    undo: [],
    redo: [],
  };
}

export function outlineFrom(document: DocumentSnapshot): OutlineEntry[] {
  const entries: OutlineEntry[] = [];
  document.blocks.forEach((block, index) => {
    if (block.kind !== "scene_heading") {
      return;
    }
    const later = document.blocks.slice(index + 1).find((item) => item.text.trim() && item.kind !== "scene_heading");
    entries.push({
      sceneId: block.id,
      sceneNumber: String(entries.length + 1),
      heading: block.text,
      blockId: block.id,
      summary: later?.text ?? "",
    });
  });
  return entries;
}

export function cardsFrom(document: DocumentSnapshot): SceneCard[] {
  return outlineFrom(document).map((entry) => ({
    sceneId: entry.sceneId,
    heading: entry.heading,
    summary: entry.summary,
    blockIds: document.blocks.map((block) => block.id),
  }));
}

function nextId(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function applyTransition(blocks: BlockSnapshot[], blockId: string, key: "Enter" | "Tab"): BlockSnapshot[] {
  const table = key === "Enter" ? ENTER_TRANSITIONS : TAB_TRANSITIONS;
  const index = blocks.findIndex((block) => block.id === blockId);
  if (index < 0) {
    return blocks;
  }
  const kind = table[blocks[index].kind];
  if (!kind) {
    return blocks;
  }
  const inserted: BlockSnapshot = { id: nextId("blk"), kind: kind as BlockKind, text: "" };
  return [...blocks.slice(0, index + 1), inserted, ...blocks.slice(index + 1)];
}

export function reduceSession(state: EditorSessionState, command: EditorCommand): EditorSessionState {
  const safe = assertCommandIsNotCanonSave(command);
  const document = { ...state.document, blocks: [...state.document.blocks], notes: [...state.document.notes] };
  let liveMessage = commandLabelSafe(safe);
  let selectedBlockId = state.selectedBlockId;
  let mode = state.mode;
  let airplane = state.airplane;
  const undo = [...state.undo];
  const redo = safe.type === "undo" || safe.type === "redo" ? state.redo : [];

  if (safe.type === "update_text") {
    document.blocks = document.blocks.map((block) =>
      block.id === safe.blockId ? { ...block, text: safe.text } : block
    );
    document.revisionId = nextId("rev");
    undo.push(safe);
  } else if (safe.type === "transition") {
    document.blocks = applyTransition(document.blocks, safe.blockId, safe.key);
    document.revisionId = nextId("rev");
    const index = document.blocks.findIndex((block) => block.id === safe.blockId);
    selectedBlockId = document.blocks[index + 1]?.id ?? selectedBlockId;
    undo.push(safe);
  } else if (safe.type === "replace" && safe.query) {
    document.blocks = document.blocks.map((block) => ({
      ...block,
      text: block.text.split(safe.query).join(safe.replacement),
    }));
    document.revisionId = nextId("rev");
    undo.push(safe);
  } else if (safe.type === "add_note") {
    const note: NoteSnapshot = { id: nextId("note"), blockId: safe.blockId, text: safe.text };
    document.notes = [...document.notes, note];
    document.revisionId = nextId("rev");
  } else if (safe.type === "set_mode") {
    mode = safe.mode;
    liveMessage = safe.mode === "author" ? "Author mode. Chrome reduced." : "Review mode.";
  } else if (safe.type === "set_airplane") {
    airplane = safe.enabled;
    liveMessage = safe.enabled ? "Airplane mode. Local save remains available." : "Airplane mode off.";
  } else if (safe.type === "contextual") {
    document.notes = [
      ...document.notes,
      { id: nextId("note"), blockId: safe.blockId, text: `${safe.action.toUpperCase()}: creator-owned` },
    ];
  } else if (safe.type === "recover") {
    liveMessage = "Recovery journal replayed.";
  }

  return {
    ...state,
    document,
    mode,
    airplane,
    selectedBlockId,
    liveMessage,
    commands: [...state.commands, safe],
    undo: safe.type === "undo" ? undo.slice(0, -1) : undo,
    redo,
  };
}

function commandLabelSafe(command: EditorCommand): string {
  if (command.type === "update_text") {
    return "Saved locally.";
  }
  if (command.type === "transition") {
    return `${command.key} inserted a typed element.`;
  }
  return "Command applied.";
}

export function searchHits(document: DocumentSnapshot, query: string): { blockId: string; text: string }[] {
  if (!query) {
    return [];
  }
  return document.blocks
    .filter((block) => block.text.includes(query))
    .map((block) => ({ blockId: block.id, text: block.text }));
}
