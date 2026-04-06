"use client";

import { useState, useEffect, type FormEvent } from "react";
import { Loader2 } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { createUser, updateUser, uploadUserAvatar, type UserDetail } from "@/lib/api";

interface UserFormModalProps {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  user?: UserDetail | null;
}

const ROLES = [
  { value: "admin", label: "Администратор" },
  { value: "manager", label: "Менеджер" },
  { value: "engineer", label: "Инженер" },
  { value: "warehouse_manager", label: "Кладовщик" },
  { value: "accountant", label: "Бухгалтер" },
];

/**
 * Modal form for creating/editing users.
 *
 * Модальная форма создания и редактирования пользователей.
 *
 * Args:
 *     open: Открыт ли модал.
 *     onClose: Callback закрытия.
 *     onSaved: Callback после сохранения.
 *     user: Пользователь для редактирования (null для создания).
 */
export function UserFormModal({ open, onClose, onSaved, user }: UserFormModalProps) {
  const isEdit = !!user;
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("engineer");
  const [phone, setPhone] = useState("");
  const [position, setPosition] = useState("");
  const [avatarUrl, setAvatarUrl] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [avatarFile, setAvatarFile] = useState<File | null>(null);

  useEffect(() => {
    if (!open) return;
    if (user) {
      setFullName(user.full_name);
      setEmail(user.email);
      setPassword("");
      setRole(user.role);
      setPhone(user.phone ?? "");
      setPosition(user.position ?? "");
      setAvatarUrl(user.avatar_url ?? "");
      setIsActive(user.is_active);
      setAvatarFile(null);
    } else {
      setFullName("");
      setEmail("");
      setPassword("");
      setRole("engineer");
      setPhone("");
      setPosition("");
      setAvatarUrl("");
      setIsActive(true);
      setAvatarFile(null);
    }
    setError(null);
  }, [open, user]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      if (isEdit && user) {
        const payload: Record<string, unknown> = {};
        if (fullName !== user.full_name) payload.full_name = fullName;
        if (role !== user.role) payload.role = role;
        if (phone !== (user.phone ?? "")) payload.phone = phone || null;
        if (position !== (user.position ?? "")) payload.position = position || null;
        if (avatarUrl !== (user.avatar_url ?? "")) payload.avatar_url = avatarUrl || null;
        if (isActive !== user.is_active) payload.is_active = isActive;
        if (password.trim().length >= 6) payload.password = password.trim();
        let saved = user;
        if (Object.keys(payload).length > 0) {
          saved = await updateUser(user.id, payload);
        }
        if (avatarFile) {
          await uploadUserAvatar(saved.id, avatarFile);
        }
      } else {
        const created = await createUser({
          email,
          full_name: fullName,
          password,
          role,
          phone: phone || null,
          position: position || null,
          avatar_url: avatarUrl || null,
        });
        if (avatarFile) {
          await uploadUserAvatar(created.id, avatarFile);
        }
      }
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEdit ? "Редактировать пользователя" : "Новый пользователь"}
      className="sm:max-w-lg"
      footer={
        <>
          <button type="button" onClick={onClose} disabled={submitting} className="btn-ghost">Отмена</button>
          <button type="submit" form="user-form" disabled={submitting} className="btn-primary gap-1.5">
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {isEdit ? "Сохранить" : "Создать"}
          </button>
        </>
      }
    >
      <form id="user-form" onSubmit={handleSubmit} className="space-y-4">
        {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>}

        <div>
          <label className="mb-1 block text-sm font-medium text-surface-700">ФИО <span className="text-red-500">*</span></label>
          <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} className="input" required />
        </div>

        {!isEdit && (
          <>
            <div>
              <label className="mb-1 block text-sm font-medium text-surface-700">Email <span className="text-red-500">*</span></label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="input" required />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-surface-700">Пароль <span className="text-red-500">*</span></label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="input" required minLength={6} />
            </div>
          </>
        )}

        {isEdit && (
          <div>
            <label className="mb-1 block text-sm font-medium text-surface-700">Новый пароль (Keycloak)</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input"
              minLength={6}
              autoComplete="new-password"
              placeholder="Не менять — оставьте пустым"
            />
            <p className="mt-1 text-xs text-surface-500">
              Хранится только в Keycloak. Минимум 6 символов, если задаёте новый пароль.
            </p>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-surface-700">Роль</label>
            <select value={role} onChange={(e) => setRole(e.target.value)} className="input">
              {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-surface-700">Должность</label>
            <input type="text" value={position} onChange={(e) => setPosition(e.target.value)} className="input" placeholder="Должность" />
          </div>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-surface-700">Телефон</label>
          <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} className="input" placeholder="+7..." />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-surface-700">Фото (URL)</label>
          <input type="url" value={avatarUrl} onChange={(e) => setAvatarUrl(e.target.value)} className="input" placeholder="https://..." />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-surface-700">Фото (файл)</label>
          <input
            type="file"
            accept="image/*"
            onChange={(e) => setAvatarFile(e.target.files?.[0] ?? null)}
            className="input"
          />
        </div>

        {isEdit && (
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)}
              className="h-4 w-4 rounded border-surface-300 text-primary-600" />
            <span className="text-sm font-medium text-surface-700">Активен</span>
          </label>
        )}
      </form>
    </Modal>
  );
}

export default UserFormModal;
