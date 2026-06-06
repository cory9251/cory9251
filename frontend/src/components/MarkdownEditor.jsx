import React, { useRef, useState } from "react";
import { TextB, TextItalic, ListBullets, ListNumbers, TextH, LinkSimple, Eye, PencilSimple } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import MarkdownView from "./MarkdownView";

// Module-scope so React doesn't recreate this component on every render
function ToolbarBtn({ onClick, icon: Icon, label, testId }) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      aria-label={label}
      title={label}
      className="grid h-8 w-8 place-items-center text-[#4B5563] hover:bg-[#F0F4FF] hover:text-[#0044FF]"
    >
      <Icon size={14} weight="bold" />
    </button>
  );
}

/**
 * MarkdownEditor — light-weight markdown editor with formatting toolbar +
 * Write / Preview tab toggle. Stores plain markdown in the value prop.
 *
 * Used by CreateGigDialog and EditGigDialog for the gig description field.
 */
export default function MarkdownEditor({
  value,
  onChange,
  placeholder,
  testIdPrefix = "md",
  rows = 6,
  maxLength = 4000,
}) {
  const [tab, setTab] = useState("write");
  const taRef = useRef(null);

  const wrap = (before, after = before) => {
    const ta = taRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const selected = value.slice(start, end);
    const next =
      value.slice(0, start) + before + selected + after + value.slice(end);
    onChange(next);
    // Restore cursor inside the wrapped text
    requestAnimationFrame(() => {
      ta.focus();
      ta.selectionStart = start + before.length;
      ta.selectionEnd = end + before.length;
    });
  };

  const prefixLines = (prefix) => {
    const ta = taRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    // Expand to whole lines
    const before = value.slice(0, start);
    const after = value.slice(end);
    const lineStart = before.lastIndexOf("\n") + 1;
    const lineEnd = end + after.indexOf("\n");
    const realEnd = lineEnd >= start ? (after.indexOf("\n") === -1 ? value.length : lineEnd) : value.length;
    const block = value.slice(lineStart, realEnd);
    const prefixed = block
      .split("\n")
      .map((ln, i) =>
        prefix === "1. " ? `${i + 1}. ${ln}` : `${prefix}${ln}`
      )
      .join("\n");
    const next = value.slice(0, lineStart) + prefixed + value.slice(realEnd);
    onChange(next);
    requestAnimationFrame(() => ta.focus());
  };

  const insertLink = () => {
    const url = window.prompt("Link URL");
    if (!url) return;
    wrap("[", `](${url})`);
  };

  return (
    <div
      data-testid={`${testIdPrefix}-editor`}
      className="overflow-hidden border border-[#030712]"
    >
      <div className="flex items-center justify-between border-b border-[#E5E7EB] bg-[#F9FAFB]">
        {/* Write / Preview tabs */}
        <div className="flex">
          <button
            type="button"
            data-testid={`${testIdPrefix}-tab-write`}
            onClick={() => setTab("write")}
            className={`flex items-center gap-1 px-3 py-1.5 font-mono-label text-[10px] tracking-[0.18em] ${
              tab === "write"
                ? "bg-white text-[#030712]"
                : "text-[#4B5563] hover:text-[#030712]"
            }`}
          >
            <PencilSimple size={11} weight="bold" /> Write
          </button>
          <button
            type="button"
            data-testid={`${testIdPrefix}-tab-preview`}
            onClick={() => setTab("preview")}
            className={`flex items-center gap-1 px-3 py-1.5 font-mono-label text-[10px] tracking-[0.18em] ${
              tab === "preview"
                ? "bg-white text-[#030712]"
                : "text-[#4B5563] hover:text-[#030712]"
            }`}
          >
            <Eye size={11} weight="bold" /> Preview
          </button>
        </div>
        {/* Toolbar */}
        {tab === "write" && (
          <div className="flex items-center pr-1">
            <ToolbarBtn
              onClick={() => wrap("**")}
              icon={TextB}
              label="Bold"
              testId={`${testIdPrefix}-btn-bold`}
            />
            <ToolbarBtn
              onClick={() => wrap("_")}
              icon={TextItalic}
              label="Italic"
              testId={`${testIdPrefix}-btn-italic`}
            />
            <ToolbarBtn
              onClick={() => prefixLines("### ")}
              icon={TextH}
              label="Heading"
              testId={`${testIdPrefix}-btn-heading`}
            />
            <ToolbarBtn
              onClick={() => prefixLines("- ")}
              icon={ListBullets}
              label="Bullet list"
              testId={`${testIdPrefix}-btn-bullets`}
            />
            <ToolbarBtn
              onClick={() => prefixLines("1. ")}
              icon={ListNumbers}
              label="Numbered list"
              testId={`${testIdPrefix}-btn-numbered`}
            />
            <ToolbarBtn
              onClick={insertLink}
              icon={LinkSimple}
              label="Link"
              testId={`${testIdPrefix}-btn-link`}
            />
          </div>
        )}
      </div>
      {tab === "write" ? (
        <Textarea
          ref={taRef}
          data-testid={`${testIdPrefix}-textarea`}
          value={value}
          onChange={(e) => onChange(e.target.value.slice(0, maxLength))}
          placeholder={placeholder}
          rows={rows}
          className="rounded-none border-0 px-3 py-2 focus-visible:ring-0"
        />
      ) : (
        <div
          data-testid={`${testIdPrefix}-preview`}
          className="min-h-[120px] px-3 py-2 text-sm"
        >
          {value.trim() ? (
            <MarkdownView text={value} />
          ) : (
            <div className="text-xs text-[#9CA3AF]">
              Nothing to preview yet — switch back to Write and start typing.
            </div>
          )}
        </div>
      )}
      <div className="flex items-center justify-between border-t border-[#E5E7EB] bg-[#F9FAFB] px-3 py-1.5">
        <span className="font-mono-label text-[9px] text-[#4B5563]">
          Markdown · **bold**, _italic_, - bullet
        </span>
        <span className="text-[9px] text-[#9CA3AF]">
          {value.length}/{maxLength}
        </span>
      </div>
    </div>
  );
}
