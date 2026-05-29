import React, { useEffect, useRef, useState } from "react";
import { api, API, getErr } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/context/AuthContext";
import {
  Camera,
  IdentificationCard,
  CheckCircle,
  UserCircle,
  UploadSimple,
} from "@phosphor-icons/react";

export default function WorkerProfile() {
  const { user, checkAuth } = useAuth();
  const [form, setForm] = useState({
    name: user?.name || "",
    phone: user?.phone || "",
    address: user?.address || "",
    bio: user?.bio || "",
    skills: (user?.skills || []).join(", "),
  });
  const [saving, setSaving] = useState(false);
  const avatarInput = useRef(null);
  const idInput = useRef(null);

  useEffect(() => {
    if (user) {
      setForm({
        name: user.name || "",
        phone: user.phone || "",
        address: user.address || "",
        bio: user.bio || "",
        skills: (user.skills || []).join(", "),
      });
    }
  }, [user]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.put("/profile", {
        ...form,
        skills: form.skills
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      });
      await checkAuth();
      toast.success("Profile saved");
    } catch (e) {
      toast.error(getErr(e));
    } finally {
      setSaving(false);
    }
  };

  const uploadAvatar = async (file) => {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post("/profile/avatar", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      await checkAuth();
      toast.success("Photo updated");
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  const uploadId = async (file) => {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post("/profile/id", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      await checkAuth();
      toast.success("ID uploaded — pending verification");
    } catch (e) {
      toast.error(getErr(e));
    }
  };

  if (!user) return null;

  return (
    <div className="px-5 py-6" data-testid="worker-profile">
      <div className="font-mono-label">My profile</div>
      <h1 className="mt-1 font-display text-3xl font-black tracking-tight">{user.name}</h1>

      {/* Avatar + ID Section */}
      <div className="mt-6 gb-tactile rounded-2xl border border-black/5 bg-white p-5">
        <div className="flex items-center gap-4">
          <div className="relative">
            <div className="grid h-20 w-20 place-items-center overflow-hidden rounded-2xl bg-[#F0F4FF] text-[#0044FF]">
              {user.avatar_path ? (
                <ProtectedImg path={user.avatar_path} />
              ) : (
                <UserCircle size={50} weight="duotone" />
              )}
            </div>
            <button
              data-testid="upload-avatar-btn"
              onClick={() => avatarInput.current?.click()}
              className="absolute -bottom-2 -right-2 grid h-8 w-8 place-items-center rounded-full bg-[#030712] text-white"
            >
              <Camera size={14} weight="fill" />
            </button>
            <input
              ref={avatarInput}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => uploadAvatar(e.target.files?.[0])}
            />
          </div>
          <div>
            <div className="font-display text-lg font-bold">{user.name}</div>
            <div className="text-xs text-[#4B5563]">{user.email}</div>
          </div>
        </div>

        <div className="mt-5 border-t border-[#E5E7EB] pt-4">
          <div className="font-mono-label mb-2 flex items-center gap-2">
            <IdentificationCard size={14} weight="duotone" /> Government ID
          </div>
          {user.id_image_path ? (
            <div>
              <div className="overflow-hidden rounded-xl border border-[#E5E7EB]">
                <ProtectedImg path={user.id_image_path} className="w-full" />
              </div>
              <div className="mt-2 flex items-center justify-between text-xs">
                {user.id_verified ? (
                  <span className="inline-flex items-center gap-1 text-[#10B981]">
                    <CheckCircle size={12} weight="fill" /> Verified
                  </span>
                ) : (
                  <span className="text-[#F59E0B] font-semibold">Pending verification</span>
                )}
                <button
                  data-testid="replace-id-btn"
                  onClick={() => idInput.current?.click()}
                  className="font-semibold text-[#0044FF]"
                >
                  Replace
                </button>
              </div>
            </div>
          ) : (
            <button
              data-testid="upload-id-dropzone"
              onClick={() => idInput.current?.click()}
              className="gb-dropzone flex w-full flex-col items-center justify-center rounded-xl bg-white p-6 text-center"
            >
              <UploadSimple size={28} weight="duotone" className="text-[#0044FF]" />
              <div className="mt-2 text-sm font-semibold">Upload a photo of your ID</div>
              <div className="mt-1 text-xs text-[#4B5563]">JPG, PNG · 1 image</div>
            </button>
          )}
          <input
            ref={idInput}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => uploadId(e.target.files?.[0])}
          />
        </div>
      </div>

      {/* Details form */}
      <form
        onSubmit={save}
        className="mt-6 gb-tactile space-y-4 rounded-2xl border border-black/5 bg-white p-5"
      >
        <div>
          <Label className="font-mono-label">Full name</Label>
          <Input
            data-testid="profile-name"
            value={form.name}
            onChange={(e) => set("name", e.target.value)}
            className="mt-2 h-11 rounded-xl border-[#E5E7EB]"
          />
        </div>
        <div>
          <Label className="font-mono-label">Phone</Label>
          <Input
            data-testid="profile-phone"
            value={form.phone}
            onChange={(e) => set("phone", e.target.value)}
            placeholder="+1 555 …"
            className="mt-2 h-11 rounded-xl border-[#E5E7EB]"
          />
        </div>
        <div>
          <Label className="font-mono-label">Address</Label>
          <Input
            data-testid="profile-address"
            value={form.address}
            onChange={(e) => set("address", e.target.value)}
            className="mt-2 h-11 rounded-xl border-[#E5E7EB]"
          />
        </div>
        <div>
          <Label className="font-mono-label">Skills (comma separated)</Label>
          <Input
            data-testid="profile-skills"
            value={form.skills}
            onChange={(e) => set("skills", e.target.value)}
            placeholder="deep cleaning, driving, lifting…"
            className="mt-2 h-11 rounded-xl border-[#E5E7EB]"
          />
        </div>
        <div>
          <Label className="font-mono-label">Bio</Label>
          <Textarea
            data-testid="profile-bio"
            value={form.bio}
            onChange={(e) => set("bio", e.target.value)}
            rows={3}
            className="mt-2 rounded-xl border-[#E5E7EB]"
            placeholder="Tell your manager a bit about you…"
          />
        </div>
        <Button
          data-testid="save-profile-btn"
          type="submit"
          disabled={saving}
          className="h-12 w-full rounded-2xl bg-[#030712] text-white"
        >
          {saving ? "Saving…" : "Save profile"}
        </Button>
      </form>
    </div>
  );
}

function ProtectedImg({ path, className = "h-full w-full object-cover" }) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let url = null;
    (async () => {
      try {
        const res = await fetch(`${API}/files/${path}`, {
          credentials: "include",
        });
        if (!res.ok) return;
        const b = await res.blob();
        url = URL.createObjectURL(b);
        setSrc(url);
      } catch {}
    })();
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [path]);
  if (!src) return <div className="h-full w-full bg-[#F0F4FF]" />;
  return <img src={src} alt="" className={className} />;
}
