/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom/vitest" />

import { render } from "@testing-library/react";
import { screen } from "@testing-library/dom";
import Home from "../app/page";

describe("Home page", () => {
  it("renders the AnalytIQ brand name", () => {
    render(<Home />);
    expect(screen.getByRole("heading", { name: /analytiq/i })).toBeInTheDocument();
  });

  it("renders the project tagline", () => {
    render(<Home />);
    expect(screen.getByText(/intelligent analysis\. verified insights\./i)).toBeInTheDocument();
  });

  it("renders the project description", () => {
    render(<Home />);
    expect(
      screen.getByText(/evidence-grounded.*multi-agent.*ai data analytics/i)
    ).toBeInTheDocument();
  });

  it("displays the under development notice", () => {
    render(<Home />);
    expect(screen.getByText(/under development/i)).toBeInTheDocument();
  });

  it("uses a main landmark element", () => {
    render(<Home />);
    expect(screen.getByRole("main")).toBeInTheDocument();
  });
});
