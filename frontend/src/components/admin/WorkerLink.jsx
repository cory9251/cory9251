import React from "react";

/**
 * Renders a worker's name as a clickable link to /ops/workers/{worker_id}.
 * Opens in a new tab so the admin doesn't lose their place on a gig/project/report.
 * Falls back to plain text when worker_id is missing.
 */
export default function WorkerLink({
  workerId,
  name,
  className = "",
  children,
}) {
  const label = children ?? name ?? "—";
  if (!workerId) {
    return <span className={className}>{label}</span>;
  }
  return (
    <a
      href={`/ops/workers/${workerId}`}
      target="_blank"
      rel="noopener noreferrer"
      data-testid={`worker-link-${workerId}`}
      className={`underline decoration-dotted underline-offset-4 hover:text-[#0044FF] hover:decoration-solid ${className}`}
      onClick={(e) => {
        // stop bubbling so we don't trigger parent row's onClick handler
        e.stopPropagation();
      }}
    >
      {label}
    </a>
  );
}
