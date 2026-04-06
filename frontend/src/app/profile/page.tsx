"use client";

import { useEffect, useState, useCallback, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { User as UserIcon, Loader2, Camera } from "lucide-react";
import {
  fetchCurrentUser,
  updateCurrentUserProfile,
  uploadUserAvatar,
  ApiError,
  type UserDetail,
} from "@/lib/api";
import { useAuthStore } from "@/stores/auth";
import type { User as AuthUser } from "@/types";

function detailToAuthUser(d: UserDetail): AuthUser {
  return {
    id: d.id,
    email: d.email,
    full_name: d.full_name,
    role: d.role as AuthUser["role"],
    is_active: d.is_active,
    avatar_url: d.avatar_url ?? undefined,
    phone: d.phone ?? undefined,
    created_at: d.created_at,
    updated_at: d.updated_at,
  };
}

function avatarSrcForDisplay(url: string | null | undefined, cacheBust?: string): string | undefined {
  if (!url) return undefined;
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  const base = url.includes("?") ? `${url}&` : `${url}?`;
  return cacheBust ? `${base}cb=${encodeURIComponent(cacheBust)}` : url;
}

export default function ProfilePage() {
  const router = useRouter();
  const authUser = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const isLoadingAuth = useAuthStore((s) => s.isLoading);

  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<UserDetail | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await fetchCurrentUser();
      setDetail(d);
      setFullName(d.full_name);
      setPhone(d.phone ?? "");
    } catch {
      if (authUser) {
        setFullName(authUser.full_name);
        setPhone(authUser.phone ?? "");
      }
      setError("Не удалось загрузить профиль");
    } finally {
      setLoading(false);
    }
  }, [authUser]);

  useEffect(() => {
    if (!isLoadingAuth && !authUser) {
      router.replace("/login");
      return;
    }
    if (authUser) {
      void load();
    }
  }, [authUser, isLoadingAuth, router, load]);

  useEffect(() => {
    if (!avatarFile) {
      setAvatarPreview(null);
      return;
    }
    const url = URL.createObjectURL(avatarFile);
    setAvatarPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [avatarFile]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!authUser) return;
    setSaving(true);
    setError(null);
    try {
      let latest: UserDetail | null = null;
      const patch: { phone?: string | null; full_name?: string | null } = {};
      const nameTrim = fullName.trim();
      const phoneNorm = phone.trim() || null;
      const prevName = detail?.full_name ?? authUser.full_name;
      const prevPhone = detail?.phone ?? authUser.phone ?? null;
      if (nameTrim !== prevName) patch.full_name = nameTrim;
      if (phoneNorm !== prevPhone) patch.phone = phoneNorm;

      if (Object.keys(patch).length > 0) {
        latest = await updateCurrentUserProfile(patch);
      }
      if (avatarFile) {
        latest = await uploadUserAvatar(authUser.id, avatarFile);
      }
      if (latest) {
        setDetail(latest);
        setUser(detailToAuthUser(latest));
      } else {
        const d = await fetchCurrentUser();
        setDetail(d);
        setUser(detailToAuthUser(d));
      }
      setAvatarFile(null);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Не удалось сохранить",
      );
    } finally {
      setSaving(false);
    }
  }

  const displayAvatarUrl = avatarPreview ?? avatarSrcForDisplay(detail?.avatar_url ?? authUser?.avatar_url, detail?.updated_at ?? authUser?.updated_at);

  const initials = (authUser?.full_name ?? fullName)
    .split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  if (isLoadingAuth || loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center p-6">
        <Loader2 className="h-8 w-8 animate-spin text-surface-400" />
      </div>
    );
  }

  if (!authUser) {
    return null;
  }

  return (
    <div className="mx-auto max-w-lg space-y-6 p-4 pb-24 lg:p-6">
      <div>
        <h1 className="text-2xl font-bold text-surface-900">Профиль</h1>
        <p className="mt-1 text-sm text-surface-500">Фото и телефон видны в системе при работе с задачами и командой.</p>
      </div>

      <form onSubmit={handleSubmit} className="card space-y-5 p-5">
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
            {error}
          </div>
        )}

        <div className="flex flex-col items-center gap-3 sm:flex-row sm:items-start">
          <div className="relative">
            {displayAvatarUrl ? (
              <img
                src={displayAvatarUrl}
                alt=""
                className="h-24 w-24 rounded-full border border-surface-200 object-cover"
              />
            ) : (
              <div className="flex h-24 w-24 items-center justify-center rounded-full bg-primary-600 text-xl font-semibold text-white">
                {initials || <UserIcon className="h-10 w-10 opacity-90" />}
              </div>
            )}
            <label
              className="absolute bottom-0 right-0 flex h-9 w-9 cursor-pointer items-center justify-center rounded-full border border-surface-200 bg-white shadow-sm transition hover:bg-surface-50"
              title="Загрузить фото"
            >
              <Camera className="h-4 w-4 text-surface-600" />
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif"
                className="sr-only"
                onChange={(ev) => {
                  const f = ev.target.files?.[0];
                  if (f) {
                    if (f.size > 5 * 1024 * 1024) {
                      setError("Файл не больше 5 МБ");
                      return;
                    }
                    setAvatarFile(f);
                    setError(null);
                  }
                  ev.target.value = "";
                }}
              />
            </label>
          </div>
          <div className="min-w-0 flex-1 text-center text-sm text-surface-500 sm:text-left">
            <p>JPEG, PNG, WebP или GIF, до 5 МБ.</p>
            {avatarFile && (
              <button
                type="button"
                className="mt-2 text-primary-600 hover:underline"
                onClick={() => setAvatarFile(null)}
              >
                Отменить новое фото
              </button>
            )}
          </div>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-surface-700">Имя</label>
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="input w-full"
            required
            minLength={1}
            autoComplete="name"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-surface-700">Телефон</label>
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="input w-full"
            placeholder="+7 …"
            autoComplete="tel"
          />
        </div>

        <div className="rounded-lg bg-surface-50 px-3 py-2 text-sm text-surface-600">
          <span className="font-medium text-surface-700">Email</span>
          <p className="mt-0.5">{authUser.email}</p>
          <p className="mt-2 text-xs text-surface-400">Смена email — через администратора.</p>
        </div>

        <button type="submit" className="btn-primary w-full gap-2 sm:w-auto" disabled={saving || loading}>
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Сохранить
        </button>
      </form>
    </div>
  );
}
