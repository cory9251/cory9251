import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChatCircleDots, CircleNotch } from "@phosphor-icons/react";
import { toast } from "sonner";
import { api, getErr } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

/**
 * One-click "Message {user}" — opens-or-creates a DM thread, then navigates
 * to the existing Messages page with the thread pre-selected.
 *
 * Usage:
 *   <MessageUserButton userId={w.user_id} />                   // full button
 *   <MessageUserButton userId={w.user_id} variant="icon" />    // 28px icon
 *   <MessageUserButton userId={w.user_id} variant="row" />     // table row
 *
 * Notes:
 *   - Stops event propagation so it can sit inside clickable cards/rows.
 *   - Uses the user's role to pick the right /messages route (admin/va/crew).
 *   - Backend gating (`POST /messages/threads/dm`) decides who can DM whom;
 *     this component just surfaces the action.
 */
export default function MessageUserButton({
  userId,
  name,
  variant = "default", // 'default' | 'icon' | 'row' | 'compact'
  className = "",
  testId,
  label,
}) {
  const { user } = useAuth();
  const nav = useNavigate();
  const [busy, setBusy] = useState(false);

  if (!userId || userId === user?.user_id) return null;

  const portal =
    user?.role === "admin"
      ? "/ops/messages"
      : user?.role === "va"
      ? "/va/messages"
      : "/crew/messages";

  const open = async (e) => {
    if (e) {
      e.stopPropagation();
      e.preventDefault();
    }
    if (busy) return;
    setBusy(true);
    try {
      const { data } = await api.post("/messages/threads/dm", { user_id: userId });
      nav(`${portal}?thread=${data.thread_id}`);
    } catch (err) {
      toast.error(getErr(err));
    } finally {
      setBusy(false);
    }
  };

  const tid = testId || `message-user-${userId}`;

  if (variant === "icon") {
    return (
      <button
        type="button"
        data-testid={tid}
        onClick={open}
        disabled={busy}
        title={name ? `Message ${name}` : "Message"}
        aria-label={name ? `Message ${name}` : "Message"}
        className={`grid h-8 w-8 place-items-center border border-[#E5E7EB] bg-white text-[#0044FF] transition-colors hover:border-[#0044FF] hover:bg-[#0044FF] hover:text-white disabled:opacity-50 ${className}`}
      >
        {busy ? (
          <CircleNotch size={14} className="animate-spin" weight="bold" />
        ) : (
          <ChatCircleDots size={14} weight="duotone" />
        )}
      </button>
    );
  }

  if (variant === "row") {
    return (
      <button
        type="button"
        data-testid={tid}
        onClick={open}
        disabled={busy}
        title={name ? `Message ${name}` : "Message"}
        className={`inline-flex items-center gap-1 border border-[#0044FF] bg-white px-2 py-1 text-xs text-[#0044FF] transition-colors hover:bg-[#0044FF] hover:text-white disabled:opacity-50 ${className}`}
      >
        {busy ? (
          <CircleNotch size={11} className="animate-spin" weight="bold" />
        ) : (
          <ChatCircleDots size={11} weight="bold" />
        )}
        {label || "Message"}
      </button>
    );
  }

  if (variant === "compact") {
    return (
      <button
        type="button"
        data-testid={tid}
        onClick={open}
        disabled={busy}
        className={`inline-flex items-center gap-1 text-xs font-semibold text-[#0044FF] underline-offset-2 hover:underline disabled:opacity-50 ${className}`}
      >
        {busy ? (
          <CircleNotch size={11} className="animate-spin" weight="bold" />
        ) : (
          <ChatCircleDots size={11} weight="bold" />
        )}
        {label || "Message"}
      </button>
    );
  }

  // default — full-width outline button
  return (
    <button
      type="button"
      data-testid={tid}
      onClick={open}
      disabled={busy}
      className={`inline-flex h-11 items-center justify-center gap-2 border border-[#030712] bg-white px-4 text-sm font-semibold text-[#030712] transition-colors hover:bg-[#030712] hover:text-white disabled:opacity-50 ${className}`}
    >
      {busy ? (
        <CircleNotch size={16} className="animate-spin" weight="bold" />
      ) : (
        <ChatCircleDots size={16} weight="duotone" />
      )}
      {label || (name ? `Message ${name}` : "Message")}
    </button>
  );
}
