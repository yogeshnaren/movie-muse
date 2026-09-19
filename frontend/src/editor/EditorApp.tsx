import React, { useMemo, useState } from "react";
import { cardsFrom, initialSession, outlineFrom, reduceSession, searchHits } from "./session";
import type { AuthorMode, ContextualAction, EditorCommand } from "./types";

function dispatchFactory(
  setState: React.Dispatch<React.SetStateAction<ReturnType<typeof initialSession>>>
) {
  return (command: EditorCommand) => {
    setState((current) => reduceSession(current, command));
  };
}

export function EditorApp() {
  const [state, setState] = useState(initialSession);
  const dispatch = useMemo(() => dispatchFactory(setState), []);
  const outline = outlineFrom(state.document);
  const cards = cardsFrom(state.document);
  const hits = searchHits(state.document, state.query);
  const selected = state.document.blocks.find((block) => block.id === state.selectedBlockId);
  const authorClass = state.mode === "author" ? "editor-shell author-mode" : "editor-shell review-mode";

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>, blockId: string) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      dispatch({ type: "transition", blockId, key: "Enter" });
      return;
    }
    if (event.key === "Tab") {
      event.preventDefault();
      dispatch({ type: "transition", blockId, key: "Tab" });
      return;
    }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") {
      event.preventDefault();
      dispatch({ type: "undo" });
      return;
    }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "y") {
      event.preventDefault();
      dispatch({ type: "redo" });
    }
  };

  const runContextual = (action: ContextualAction) => {
    if (!selected) {
      return;
    }
    dispatch({ type: "contextual", action, blockId: selected.id });
  };

  return (
    <div className={authorClass} role="application" aria-label="Movie Muse screenplay editor">
      {state.airplane ? (
        <div className="airplane-banner" role="status">
          Airplane mode. Local save remains available through outages.
        </div>
      ) : null}
      <header className="editor-topbar">
        <h1>Movie Muse</h1>
        <p className="sr-only" aria-live="polite">
          {state.liveMessage}
        </p>
        <div className="editor-toolbar">
          <button type="button" onClick={() => dispatch({ type: "set_mode", mode: toggleMode(state.mode) })}>
            {state.mode === "author" ? "Review mode" : "Author mode"}
          </button>
          <button type="button" onClick={() => dispatch({ type: "set_airplane", enabled: !state.airplane })}>
            {state.airplane ? "Leave airplane" : "Airplane"}
          </button>
          <button type="button" onClick={() => dispatch({ type: "checkpoint", name: "draft" })}>
            Checkpoint
          </button>
          <button type="button" onClick={() => dispatch({ type: "branch", name: "explore" })}>
            Branch
          </button>
          <button type="button" onClick={() => dispatch({ type: "recover" })}>
            Recover
          </button>
        </div>
      </header>
      <div className="editor-layout">
        <aside className="outline-panel" aria-label="Scene outline">
          <h2>Outline</h2>
          <ol>
            {outline.map((entry) => (
              <li key={entry.sceneId}>
                <button type="button" onClick={() => setState((current) => ({ ...current, selectedBlockId: entry.blockId }))}>
                  {entry.heading}
                </button>
              </li>
            ))}
          </ol>
          <h2>Cards</h2>
          <ul>
            {cards.map((card) => (
              <li key={card.sceneId}>
                <strong>{card.heading}</strong>
                <p>{card.summary}</p>
              </li>
            ))}
          </ul>
        </aside>
        <main className="screenplay-pane">
          {state.document.blocks.map((block) => (
            <label key={block.id} className={`block-row kind-${block.kind}`}>
              <span className="block-kind">{block.kind.replace("_", " ")}</span>
              <textarea
                aria-label={`${block.kind.replace("_", " ")} ${block.id}`}
                value={block.text}
                onFocus={() => setState((current) => ({ ...current, selectedBlockId: block.id }))}
                onChange={(event) => dispatch({ type: "update_text", blockId: block.id, text: event.target.value })}
                onKeyDown={(event) => onKeyDown(event, block.id)}
              />
            </label>
          ))}
        </main>
        <aside className="review-panel" aria-label="Notes and revisions">
          <h2>Search</h2>
          <input
            aria-label="Search screenplay"
            value={state.query}
            onChange={(event) => setState((current) => ({ ...current, query: event.target.value }))}
          />
          <input
            aria-label="Replacement text"
            value={state.replacement}
            onChange={(event) => setState((current) => ({ ...current, replacement: event.target.value }))}
          />
          <button
            type="button"
            onClick={() => dispatch({ type: "replace", query: state.query, replacement: state.replacement })}
          >
            Replace
          </button>
          <p>{hits.length} hits</p>
          <h2>Notes</h2>
          <ul>
            {state.document.notes.map((note) => (
              <li key={note.id}>{note.text}</li>
            ))}
          </ul>
          <button
            type="button"
            onClick={() => selected && dispatch({ type: "add_note", blockId: selected.id, text: "keep this beat" })}
          >
            Add note
          </button>
          <h2>Contextual</h2>
          <div className="contextual-actions">
            <button type="button" onClick={() => runContextual("preserve")}>
              Preserve
            </button>
            <button type="button" onClick={() => runContextual("explore")}>
              Explore
            </button>
            <button type="button" onClick={() => runContextual("lock")}>
              Lock
            </button>
            <button type="button" onClick={() => runContextual("intent")}>
              Intent
            </button>
          </div>
          <h2>Revision</h2>
          <p>Head {state.document.revisionId}</p>
          <ol aria-label="Command history">
            {state.commands.map((command, index) => (
              <li key={`${command.type}-${index}`}>{command.type}</li>
            ))}
          </ol>
        </aside>
      </div>
    </div>
  );
}

function toggleMode(mode: AuthorMode): AuthorMode {
  return mode === "author" ? "review" : "author";
}

export default EditorApp;
