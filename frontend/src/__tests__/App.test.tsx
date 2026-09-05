import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "../App";

describe("App", () => {
  it("renders the Movie Muse editor heading", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /movie muse/i })).toBeInTheDocument();
  });
});

describe("professional editor", () => {
  it("exposes an accessible application surface", () => {
    render(<App />);
    expect(screen.getByRole("application", { name: /movie muse screenplay editor/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/scene outline/i)).toBeInTheDocument();
  });

  it("toggles airplane mode without leaving the local document", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: /airplane/i }));
    expect(screen.getByRole("status")).toHaveTextContent(/airplane mode/i);
    expect(screen.getByDisplayValue(/Ada studies the lock/i)).toBeInTheDocument();
  });

  it("keeps one document when switching author and review mode", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: /review mode/i }));
    expect(screen.getByRole("button", { name: /author mode/i })).toBeInTheDocument();
    expect(screen.getByDisplayValue(/INT. KITCHEN - DAY/i)).toBeInTheDocument();
  });

  it("turns Enter into a typed element transition", async () => {
    const user = userEvent.setup();
    render(<App />);
    const action = screen.getByLabelText(/action blk_action/i);
    await user.click(action);
    await user.keyboard("{Enter}");
    expect(screen.getByRole("list", { name: /command history/i })).toHaveTextContent("transition");
  });
});
