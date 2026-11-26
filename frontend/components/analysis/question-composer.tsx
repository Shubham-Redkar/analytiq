"use client";

import React, { useState, useRef, useEffect } from "react";
import { Send, Square, Sparkles } from "lucide-react";

interface QuestionComposerProps {
  onSubmit: (question: string) => void;
  onCancel?: () => void;
  isRunning?: boolean;
  disabled?: boolean;
  suggestedQuestions?: string[];
}

export function QuestionComposer({
  onSubmit,
  onCancel,
  isRunning = false,
  disabled = false,
  suggestedQuestions = [],
}: QuestionComposerProps) {
  const [question, setQuestion] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-grow textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [question]);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (isRunning) return;
    const trimmed = question.trim();
    if (!trimmed || trimmed.length < 3) return;
    onSubmit(trimmed);
    setQuestion("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="space-y-2">
      {suggestedQuestions.length > 0 && !isRunning && (
        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-medium">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            <span>Suggested questions:</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {suggestedQuestions.map((q, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setQuestion(q);
                  textareaRef.current?.focus();
                }}
                disabled={disabled}
                className="text-xs px-3 py-1 rounded-full border bg-muted/40 hover:bg-muted text-foreground/80 hover:text-foreground transition disabled:opacity-50 cursor-pointer"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="relative flex items-end border border-input rounded-xl bg-card shadow-2xs focus-within:ring-2 focus-within:ring-primary/20 focus-within:border-primary transition">
        <textarea
          ref={textareaRef}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled || isRunning}
          rows={1}
          placeholder={disabled ? "Select a ready dataset to begin analysis..." : "Ask a question about your dataset..."}
          className="w-full resize-none bg-transparent px-4 py-3 text-[15px] leading-relaxed text-foreground placeholder:text-muted-foreground focus:outline-none max-h-40 min-h-[48px]"
        />

        <div className="p-2 shrink-0 flex items-center gap-1.5">
          {isRunning ? (
            <button
              type="button"
              onClick={onCancel}
              className="p-2.5 rounded-lg bg-rose-500 text-white hover:bg-rose-600 transition flex items-center justify-center cursor-pointer shadow-2xs"
              title="Stop analysis"
            >
              <Square className="h-4 w-4 fill-current" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={disabled || !question.trim() || question.trim().length < 3}
              className="p-2.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-40 transition flex items-center justify-center cursor-pointer shadow-2xs"
              title="Submit analytical question"
            >
              <Send className="h-4 w-4" />
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
