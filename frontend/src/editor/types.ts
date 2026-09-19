export type AuthorMode = "author" | "review";

export type ContextualAction = "preserve" | "explore" | "lock" | "intent";

export type BlockKind =
  | "scene_heading"
  | "action"
  | "character"
  | "parenthetical"
  | "dialogue"
  | "transition"
  | "shot"
  | "general"
  | "lyrics"
  | "page_break"
  | "title_page_element";

export type EditorCommand =
  | { type: "update_text"; blockId: string; text: string }
  | { type: "transition"; blockId: string; key: "Enter" | "Tab" }
  | { type: "undo" }
  | { type: "redo" }
  | { type: "search"; query: string }
  | { type: "replace"; query: string; replacement: string }
  | { type: "add_note"; blockId: string; text: string }
  | { type: "contextual"; action: ContextualAction; blockId: string }
  | { type: "checkpoint"; name: string }
  | { type: "branch"; name: string }
  | { type: "set_mode"; mode: AuthorMode }
  | { type: "set_airplane"; enabled: boolean }
  | { type: "recover" };

export type BlockSnapshot = {
  id: string;
  kind: BlockKind;
  text: string;
};

export type NoteSnapshot = {
  id: string;
  blockId: string;
  text: string;
};

export type OutlineEntry = {
  sceneId: string;
  sceneNumber: string;
  heading: string;
  blockId: string;
  summary: string;
};

export type SceneCard = {
  sceneId: string;
  heading: string;
  summary: string;
  blockIds: string[];
};

export type DocumentSnapshot = {
  id: string;
  title: string;
  revisionId: string;
  blocks: BlockSnapshot[];
  notes: NoteSnapshot[];
};

export const ENTER_TRANSITIONS: Record<string, BlockKind> = {
  scene_heading: "action",
  action: "action",
  character: "dialogue",
  parenthetical: "dialogue",
  dialogue: "action",
  transition: "scene_heading",
  shot: "action",
  general: "action",
  lyrics: "action",
};

export const TAB_TRANSITIONS: Record<string, BlockKind> = {
  action: "character",
  character: "action",
  dialogue: "parenthetical",
  parenthetical: "dialogue",
  scene_heading: "action",
  transition: "action",
};
