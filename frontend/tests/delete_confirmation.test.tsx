import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { AnalysisHistorySidebar } from "../components/analysis/analysis-history-sidebar";
import type { AnalysisSessionSummary } from "../lib/analysis-types";

describe("Analysis History Deletion Confirmation", () => {
  const mockSessions: AnalysisSessionSummary[] = [
    {
      id: "session-1",
      dataset_id: "ds-1",
      dataset_name: "Titanic",
      title: "How many passengers survived?",
      run_count: 2,
      created_at: "2026-11-26T10:00:00Z",
      updated_at: "2026-11-26T10:05:00Z",
    },
    {
      id: "session-2",
      dataset_id: "ds-1",
      dataset_name: "Titanic",
      title:
        "Average fare by class with an exceptionally long title that wraps nicely in the dialog",
      run_count: 1,
      created_at: "2026-11-26T11:00:00Z",
      updated_at: "2026-11-26T11:05:00Z",
    },
  ];

  it("opens confirmation dialog when delete button is clicked and does not immediately delete", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();

    render(
      <AnalysisHistorySidebar
        sessions={mockSessions}
        onSelectSession={vi.fn()}
        onNewSession={vi.fn()}
        onRenameSession={vi.fn()}
        onDeleteSession={onDelete}
      />
    );

    const deleteBtn = screen.getByLabelText("Delete How many passengers survived?");
    await user.click(deleteBtn);

    // Confirmation dialog should be displayed
    expect(screen.getByText("Delete analysis?")).toBeInTheDocument();
    expect(
      screen.getByText(/This will permanently delete 'How many passengers survived\?'/i)
    ).toBeInTheDocument();

    // Deletion callback must NOT have been called yet
    expect(onDelete).not.toHaveBeenCalled();
  });

  it("cancels deletion when Cancel button is clicked", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();

    render(
      <AnalysisHistorySidebar
        sessions={mockSessions}
        onSelectSession={vi.fn()}
        onNewSession={vi.fn()}
        onRenameSession={vi.fn()}
        onDeleteSession={onDelete}
      />
    );

    await user.click(screen.getByLabelText("Delete How many passengers survived?"));
    expect(screen.getByText("Delete analysis?")).toBeInTheDocument();

    const cancelBtn = screen.getByRole("button", { name: "Cancel" });
    await user.click(cancelBtn);

    await waitFor(() => {
      expect(screen.queryByText("Delete analysis?")).not.toBeInTheDocument();
    });
    expect(onDelete).not.toHaveBeenCalled();
  });

  it("executes deletion callback on explicit confirm", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn().mockResolvedValue(true);

    render(
      <AnalysisHistorySidebar
        sessions={mockSessions}
        onSelectSession={vi.fn()}
        onNewSession={vi.fn()}
        onRenameSession={vi.fn()}
        onDeleteSession={onDelete}
      />
    );

    await user.click(screen.getByLabelText("Delete How many passengers survived?"));
    const confirmBtn = screen.getByRole("button", { name: "Delete analysis" });
    await user.click(confirmBtn);

    expect(onDelete).toHaveBeenCalledWith("session-1");
  });

  it("handles long session titles gracefully in the dialog", async () => {
    const user = userEvent.setup();

    render(
      <AnalysisHistorySidebar
        sessions={mockSessions}
        onSelectSession={vi.fn()}
        onNewSession={vi.fn()}
        onRenameSession={vi.fn()}
        onDeleteSession={vi.fn()}
      />
    );

    const deleteLongBtn = screen.getByLabelText(/Delete Average fare by class/i);
    await user.click(deleteLongBtn);

    expect(screen.getByText("Delete analysis?")).toBeInTheDocument();
    expect(
      screen.getByText(
        /This will permanently delete 'Average fare by class with an exceptionally long title/i
      )
    ).toBeInTheDocument();
  });
});
