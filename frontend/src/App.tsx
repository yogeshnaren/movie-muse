import React from "react";
import { EditorApp } from "./editor/EditorApp";
import { WebShell } from "./platforms/WebShell";

function App() {
  return (
    <WebShell>
      <EditorApp />
    </WebShell>
  );
}

export default App;
