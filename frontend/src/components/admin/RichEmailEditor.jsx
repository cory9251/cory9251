/**
 * Rich text editor used by Email Blast composer.
 *
 * Built on TipTap. Toolbar: bold, italic, underline, H2, bullet/ordered
 * list, link, clear-formatting. Emits HTML that the backend uses verbatim
 * (the backend also normalizes plain text → HTML as a safety net, but
 * this editor outputs proper HTML directly so paragraphs survive Resend).
 *
 * Why HTML and not Markdown? The backend's `_email_layout` wraps the body
 * in a styled div and ships it via Resend. HTML is the lingua franca of
 * email — every client renders it.
 */
import React, { useEffect } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import {
  TextB,
  TextItalic,
  TextHOne,
  ListBullets,
  ListNumbers,
  LinkSimple,
  TextStrikethrough,
  Eraser,
} from "@phosphor-icons/react";

function ToolbarBtn({ active, onClick, title, children, testid }) {
  return (
    <button
      type="button"
      title={title}
      data-testid={testid}
      onMouseDown={(e) => {
        // Prevent the button from stealing focus from the editor (so the
        // selection is preserved when the command runs).
        e.preventDefault();
      }}
      onClick={onClick}
      className={`inline-flex h-8 w-8 items-center justify-center border transition-colors ${
        active
          ? "border-[#030712] bg-[#030712] text-white"
          : "border-[#E5E7EB] bg-white text-[#374151] hover:border-[#030712] hover:bg-[#F9FAFB]"
      }`}
    >
      {children}
    </button>
  );
}

export default function RichEmailEditor({ value, onChange, placeholder, testid }) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [2, 3] },
        // Disable bullet/orderedList from StarterKit's defaults? No — keep
        // them, but ensure their default class is null so our Tailwind
        // typography handles spacing.
        bulletList: { HTMLAttributes: { class: "bullets" } },
        orderedList: { HTMLAttributes: { class: "ordered" } },
      }),
      Link.configure({
        openOnClick: false,
        autolink: true,
        HTMLAttributes: {
          rel: "noopener noreferrer",
          class: "rich-editor-link",
        },
      }),
      Placeholder.configure({
        placeholder: placeholder || "Write your email…",
      }),
    ],
    content: value || "",
    onUpdate: ({ editor: e }) => {
      const html = e.getHTML();
      // TipTap returns "<p></p>" for empty content — normalize to ""
      onChange?.(html === "<p></p>" ? "" : html);
    },
    editorProps: {
      attributes: {
        class: "rich-email-editor-content",
        "data-testid": testid || "rich-email-editor",
      },
    },
  });

  // Sync external value changes (e.g. when admin picks a different template)
  // into the editor without breaking cursor placement during typing.
  useEffect(() => {
    if (!editor) return;
    const current = editor.getHTML();
    const next = value || "";
    // Only update when the incoming value REALLY differs — otherwise we
    // fight with the user's typing.
    if (next !== current && next !== (current === "<p></p>" ? "" : current)) {
      editor.commands.setContent(next, { emitUpdate: false });
    }
  }, [value, editor]);

  if (!editor) return null;

  const promptForLink = () => {
    const prev = editor.getAttributes("link").href;
    const url = window.prompt("Link URL (e.g. https://hcobnetwork.com/...)", prev || "https://");
    if (url === null) return;
    if (url === "") {
      editor.chain().focus().extendMarkRange("link").unsetLink().run();
      return;
    }
    editor.chain().focus().extendMarkRange("link").setLink({ href: url }).run();
  };

  return (
    <div className="rich-email-editor border border-[#030712] bg-white">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-1 border-b border-[#E5E7EB] bg-[#F9FAFB] p-2">
        <ToolbarBtn
          active={editor.isActive("bold")}
          onClick={() => editor.chain().focus().toggleBold().run()}
          title="Bold (Ctrl/Cmd + B)"
          testid="email-editor-bold"
        >
          <TextB size={14} weight="bold" />
        </ToolbarBtn>
        <ToolbarBtn
          active={editor.isActive("italic")}
          onClick={() => editor.chain().focus().toggleItalic().run()}
          title="Italic (Ctrl/Cmd + I)"
          testid="email-editor-italic"
        >
          <TextItalic size={14} weight="bold" />
        </ToolbarBtn>
        <ToolbarBtn
          active={editor.isActive("strike")}
          onClick={() => editor.chain().focus().toggleStrike().run()}
          title="Strikethrough"
          testid="email-editor-strike"
        >
          <TextStrikethrough size={14} weight="bold" />
        </ToolbarBtn>
        <div className="mx-1 h-6 w-px bg-[#E5E7EB]" />
        <ToolbarBtn
          active={editor.isActive("heading", { level: 2 })}
          onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
          title="Section heading"
          testid="email-editor-h2"
        >
          <TextHOne size={14} weight="bold" />
        </ToolbarBtn>
        <ToolbarBtn
          active={editor.isActive("bulletList")}
          onClick={() => editor.chain().focus().toggleBulletList().run()}
          title="Bulleted list"
          testid="email-editor-bullets"
        >
          <ListBullets size={14} weight="bold" />
        </ToolbarBtn>
        <ToolbarBtn
          active={editor.isActive("orderedList")}
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
          title="Numbered list"
          testid="email-editor-numbers"
        >
          <ListNumbers size={14} weight="bold" />
        </ToolbarBtn>
        <div className="mx-1 h-6 w-px bg-[#E5E7EB]" />
        <ToolbarBtn
          active={editor.isActive("link")}
          onClick={promptForLink}
          title="Add or edit link"
          testid="email-editor-link"
        >
          <LinkSimple size={14} weight="bold" />
        </ToolbarBtn>
        <div className="mx-1 h-6 w-px bg-[#E5E7EB]" />
        <ToolbarBtn
          active={false}
          onClick={() => {
            editor.chain().focus().clearNodes().unsetAllMarks().run();
          }}
          title="Clear formatting"
          testid="email-editor-clear"
        >
          <Eraser size={14} weight="bold" />
        </ToolbarBtn>
      </div>

      {/* Editor */}
      <EditorContent editor={editor} />
    </div>
  );
}
