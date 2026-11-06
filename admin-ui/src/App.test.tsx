import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import App from "./App";

it("identifies the admin workspace without requesting credentials", () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: "FoundIt admin workspace" })).toBeTruthy();
  expect(screen.queryByRole("textbox")).toBeNull();
});
