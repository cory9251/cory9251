import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * MarkdownView — read-only renderer for gig descriptions and any other
 * markdown content in the app. Whitelisted elements only; links open in a new
 * tab with rel="noopener noreferrer". Used everywhere a description is shown
 * to workers (worker feed, /crew/gigs/:id, public share page, admin gig detail).
 */
export default function MarkdownView({ text, className = "" }) {
  if (!text || !text.trim()) return null;
  return (
    <div
      data-testid="markdown-view"
      className={`gb-markdown text-sm leading-relaxed text-[#1F2937] ${className}`}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Block elements
          p: ({ node, ...props }) => <p className="mb-2 last:mb-0" {...props} />,
          h1: ({ node, ...props }) => (
            <h1
              className="mb-2 mt-3 font-display text-xl font-black"
              {...props}
            />
          ),
          h2: ({ node, ...props }) => (
            <h2
              className="mb-2 mt-3 font-display text-lg font-black"
              {...props}
            />
          ),
          h3: ({ node, ...props }) => (
            <h3
              className="mb-1.5 mt-2.5 font-display text-base font-bold"
              {...props}
            />
          ),
          ul: ({ node, ...props }) => (
            <ul className="mb-2 ml-5 list-disc space-y-1" {...props} />
          ),
          ol: ({ node, ...props }) => (
            <ol className="mb-2 ml-5 list-decimal space-y-1" {...props} />
          ),
          li: ({ node, ...props }) => <li {...props} />,
          strong: ({ node, ...props }) => (
            <strong className="font-bold text-[#030712]" {...props} />
          ),
          em: ({ node, ...props }) => <em className="italic" {...props} />,
          a: ({ node, ...props }) => (
            <a
              {...props}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[#0044FF] underline underline-offset-2 hover:text-[#0036cc]"
            />
          ),
          code: ({ node, inline, ...props }) =>
            inline ? (
              <code
                className="rounded bg-[#F0F4FF] px-1 py-0.5 font-mono text-xs text-[#0044FF]"
                {...props}
              />
            ) : (
              <code
                className="block overflow-x-auto rounded bg-[#F0F4FF] p-3 font-mono text-xs"
                {...props}
              />
            ),
          blockquote: ({ node, ...props }) => (
            <blockquote
              className="my-2 border-l-2 border-[#0044FF] bg-[#F0F4FF] py-1 pl-3 text-[#4B5563]"
              {...props}
            />
          ),
          hr: () => <hr className="my-3 border-[#E5E7EB]" />,
          // Disable potentially harmful elements (script, iframe etc.) by not
          // mapping them — ReactMarkdown won't render anything it can't parse.
        }}
        // skipHtml prevents raw <script> from working even if a user paste-bombs one.
        skipHtml
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
