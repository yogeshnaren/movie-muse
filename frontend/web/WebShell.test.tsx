import React from "react";
import { render, screen } from "@testing-library/react";
import { WebShell } from "./WebShell";

describe("web platform shell", () => {
  it("surfaces the dated web parity shell around the editor", () => {
    render(
      <WebShell>
        <p>editor child</p>
      </WebShell>
    );
    expect(screen.getByTestId("platform-web")).toBeInTheDocument();
    expect(screen.getByText("proj_01H9N49B01081040G2081040G2")).toBeInTheDocument();
    expect(screen.getByLabelText(/platform parity matrix/i)).toHaveTextContent("ios: onset_capture");
    expect(screen.getByText(/parity as of 2026-09-19/i)).toBeInTheDocument();
    expect(screen.getByText("editor child")).toBeInTheDocument();
  });
});
