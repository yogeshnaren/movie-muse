import React from "react";
import ReactDOM from "react-dom/client";
import App from "../src/App";
import "../src/index.css";
import { WebShell } from "./WebShell";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <WebShell>
      <App />
    </WebShell>
  </React.StrictMode>
);
