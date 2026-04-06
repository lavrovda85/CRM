"use client";

import { useEffect, useCallback, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ModalProps {
  /** Открыт ли модал. */
  open: boolean;
  /** Callback при закрытии. */
  onClose: () => void;
  /** Заголовок модала. */
  title?: string;
  /** Содержимое тела модала. */
  children: ReactNode;
  /** Содержимое футера (кнопки действий). */
  footer?: ReactNode;
  /** Дополнительные CSS-классы для контейнера. */
  className?: string;
}

/**
 * Адаптивный модал: на десктопе — по центру, на мобильном — выезжает снизу.
 *
 * Args:
 *     open: Флаг видимости модала.
 *     onClose: Функция закрытия.
 *     title: Заголовок.
 *     children: Содержимое тела.
 *     footer: Содержимое футера.
 *     className: Дополнительные CSS-классы.
 *
 * Returns:
 *     JSX-элемент модала или null, если закрыт.
 */
export function Modal({ open, onClose, title, children, footer, className }: ModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    },
    [onClose],
  );

  useEffect(() => {
    if (!open) return;
    document.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [open, handleKeyDown]);

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === overlayRef.current) onClose();
  };

  if (!open) return null;

  return (
    <div
      ref={overlayRef}
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 z-50 flex items-end sm:items-center sm:justify-center bg-black/40 backdrop-blur-sm animate-in fade-in"
      onClick={handleBackdropClick}
    >
      <div
        className={cn(
          "relative w-full bg-white shadow-xl",
          "rounded-t-2xl sm:rounded-2xl",
          "max-h-[90vh] sm:max-h-[85vh] sm:max-w-lg",
          "flex flex-col",
          "animate-in slide-in-from-bottom sm:slide-in-from-bottom-0 sm:zoom-in-95 duration-200",
          className,
        )}
      >
        {/* Handle bar (mobile) */}
        <div className="flex justify-center pt-2 sm:hidden">
          <div className="h-1 w-10 rounded-full bg-surface-300" />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-3 pb-2 sm:pt-5">
          {title && <h2 className="text-lg font-semibold text-surface-900">{title}</h2>}
          <button
            type="button"
            onClick={onClose}
            className="ml-auto rounded-lg p-1.5 text-surface-400 hover:bg-surface-100 hover:text-surface-600 transition-colors"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-3">{children}</div>

        {/* Footer */}
        {footer && (
          <div className="border-t border-surface-100 px-5 py-3 flex items-center justify-end gap-2">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

export default Modal;
