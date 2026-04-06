"use client";

import {
  useState,
  useRef,
  useCallback,
  type DragEvent,
  type ChangeEvent,
} from "react";
import { cn } from "@/lib/utils";
import { Upload, Camera, X, FileText, Image } from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface FileEntry {
  id: string;
  file: File;
  preview?: string;
  progress: number;
  label?: string;
}

export interface FileUploadProps {
  /** Допустимые MIME-типы (напр. "image/*,.pdf"). */
  accept?: string;
  /** Максимальное количество файлов. */
  maxFiles?: number;
  /** Максимальный размер файла в байтах. */
  maxSizeBytes?: number;
  /** Список меток для выбора (из шаблона required_documents). */
  labels?: string[];
  /** Callback при добавлении файлов. */
  onFilesAdded?: (files: FileEntry[]) => void;
  /** Callback при удалении файла. */
  onFileRemove?: (id: string) => void;
  /** Callback при смене метки файла. */
  onLabelChange?: (id: string, label: string) => void;
  className?: string;
}

let _idCounter = 0;
function nextId(): string {
  _idCounter += 1;
  return `fu-${_idCounter}-${Date.now()}`;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

/**
 * Компонент загрузки файлов с drag-and-drop, камерой, превью и выбором меток.
 *
 * Args:
 *     accept: Допустимые MIME-типы.
 *     maxFiles: Максимальное число файлов.
 *     maxSizeBytes: Лимит размера файла в байтах.
 *     labels: Массив меток документов для селекта.
 *     onFilesAdded: Callback при добавлении файлов.
 *     onFileRemove: Callback при удалении файла.
 *     onLabelChange: Callback при смене метки.
 *     className: Дополнительные CSS-классы.
 *
 * Returns:
 *     JSX-элемент компонента загрузки.
 */
export function FileUpload({
  accept,
  maxFiles = 10,
  maxSizeBytes = 20 * 1024 * 1024,
  labels,
  onFilesAdded,
  onFileRemove,
  onLabelChange,
  className,
}: FileUploadProps) {
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const cameraRef = useRef<HTMLInputElement>(null);

  const processFiles = useCallback(
    (fileList: FileList | File[]) => {
      const files = Array.from(fileList);
      const remaining = maxFiles - entries.length;
      const accepted = files.slice(0, Math.max(0, remaining));

      const newEntries: FileEntry[] = accepted
        .filter((f) => f.size <= maxSizeBytes)
        .map((file) => ({
          id: nextId(),
          file,
          preview: file.type.startsWith("image/") ? URL.createObjectURL(file) : undefined,
          progress: 0,
          label: labels?.[0],
        }));

      setEntries((prev) => [...prev, ...newEntries]);
      onFilesAdded?.(newEntries);
    },
    [entries.length, maxFiles, maxSizeBytes, labels, onFilesAdded],
  );

  const handleDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      processFiles(e.dataTransfer.files);
    },
    [processFiles],
  );

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) processFiles(e.target.files);
    e.target.value = "";
  };

  const removeFile = (id: string) => {
    setEntries((prev) => {
      const entry = prev.find((e) => e.id === id);
      if (entry?.preview) URL.revokeObjectURL(entry.preview);
      return prev.filter((e) => e.id !== id);
    });
    onFileRemove?.(id);
  };

  const isImage = (file: File) => file.type.startsWith("image/");

  return (
    <div className={cn("space-y-3", className)}>
      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        className={cn(
          "flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-6 cursor-pointer transition-colors",
          isDragOver
            ? "border-primary-400 bg-primary-50"
            : "border-surface-200 bg-surface-50 hover:border-primary-300 hover:bg-primary-50/30",
        )}
      >
        <Upload
          className={cn(
            "h-8 w-8",
            isDragOver ? "text-primary-500" : "text-surface-400",
          )}
        />
        <p className="text-sm text-surface-500">
          <span className="font-medium text-primary-600">Click to upload</span> or drag and drop
        </p>
        <p className="text-xs text-surface-400">
          Max {maxFiles} files, up to {Math.round(maxSizeBytes / (1024 * 1024))}MB each
        </p>
      </div>

      {/* Hidden inputs */}
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={accept}
        onChange={handleInputChange}
        className="hidden"
      />
      <input
        ref={cameraRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handleInputChange}
        className="hidden"
      />

      {/* Camera button (touch devices) */}
      <button
        type="button"
        onClick={() => cameraRef.current?.click()}
        className="sm:hidden flex items-center gap-2 rounded-lg border border-surface-200 px-3 py-2 text-sm text-surface-600 hover:bg-surface-50 transition-colors w-full justify-center"
      >
        <Camera className="h-4 w-4" />
        Take photo
      </button>

      {/* Preview list */}
      {entries.length > 0 && (
        <ul className="space-y-2">
          {entries.map((entry) => (
            <li
              key={entry.id}
              className="flex items-center gap-3 rounded-lg border border-surface-200 bg-white p-2"
            >
              {/* Thumbnail */}
              <div className="h-10 w-10 shrink-0 rounded-lg bg-surface-100 overflow-hidden flex items-center justify-center">
                {entry.preview ? (
                  <img src={entry.preview} alt="" className="h-full w-full object-cover" />
                ) : isImage(entry.file) ? (
                  <Image className="h-5 w-5 text-surface-400" />
                ) : (
                  <FileText className="h-5 w-5 text-surface-400" />
                )}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <p className="text-sm text-surface-700 truncate">{entry.file.name}</p>
                <p className="text-xs text-surface-400">
                  {(entry.file.size / 1024).toFixed(0)} KB
                </p>

                {/* Progress bar */}
                {entry.progress > 0 && entry.progress < 100 && (
                  <div className="mt-1 h-1 w-full rounded-full bg-surface-100">
                    <div
                      className="h-1 rounded-full bg-primary-500 transition-all"
                      style={{ width: `${entry.progress}%` }}
                    />
                  </div>
                )}
              </div>

              {/* Label selector */}
              {labels && labels.length > 0 && (
                <select
                  value={entry.label ?? ""}
                  onChange={(e) => {
                    const newLabel = e.target.value;
                    setEntries((prev) =>
                      prev.map((en) => (en.id === entry.id ? { ...en, label: newLabel } : en)),
                    );
                    onLabelChange?.(entry.id, newLabel);
                  }}
                  className="rounded-md border border-surface-200 bg-white px-2 py-1 text-xs text-surface-600 focus:outline-none focus:ring-1 focus:ring-primary-400"
                >
                  <option value="">Select label</option>
                  {labels.map((l) => (
                    <option key={l} value={l}>
                      {l}
                    </option>
                  ))}
                </select>
              )}

              {/* Remove */}
              <button
                type="button"
                onClick={() => removeFile(entry.id)}
                className="rounded-lg p-1 text-surface-400 hover:bg-red-50 hover:text-red-500 transition-colors"
                aria-label="Remove file"
              >
                <X className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default FileUpload;
