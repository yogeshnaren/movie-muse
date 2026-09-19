import React from "react";
import {
  DEEP_LINK,
  GOLDEN_PROJECT_ID,
  MIN_TOUCH_TARGET_PT,
  PARITY_AS_OF,
  PARITY_ROWS,
  WEB_LIMITATIONS
} from "./parity";

export function WebShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="platform-web" data-testid="platform-web" data-platform="web">
      <section aria-label="Web platform identity" className="platform-identity">
        <p>
          Golden project <code>{GOLDEN_PROJECT_ID}</code>
        </p>
        <p>
          Deep link <a href={DEEP_LINK}>{DEEP_LINK}</a>
        </p>
        <p>Parity as of {PARITY_AS_OF}</p>
        <p>Minimum target {MIN_TOUCH_TARGET_PT}pt</p>
        <ul aria-label="Platform parity matrix">
          {PARITY_ROWS.map((row) => (
            <li key={row.platform}>
              {row.platform}: {row.focus}
              {row.longForm ? " (long-form)" : " (onset)"}
            </li>
          ))}
        </ul>
        <p>{WEB_LIMITATIONS}</p>
        <p>Auth and subscription outages keep local authoring available.</p>
      </section>
      {children}
    </div>
  );
}
