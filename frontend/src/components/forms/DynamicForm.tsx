"use client";

import {
  useState,
  useCallback,
  useEffect,
  type ChangeEvent,
  type FormEvent,
} from "react";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export type FieldType =
  | "string"
  | "integer"
  | "decimal"
  | "enum"
  | "reference"
  | "address"
  | "date"
  | "boolean";

export interface FieldDef {
  /** Уникальный ключ поля. */
  key: string;
  /** Отображаемое название. */
  label: string;
  /** Тип поля. */
  type: FieldType;
  /** Обязательное ли. */
  is_required?: boolean;
  /** Подсказка/плейсхолдер. */
  placeholder?: string;
  /** Варианты для enum. */
  options?: { value: string; label: string }[];
  /** Асинхронная загрузка вариантов для reference. */
  loadOptions?: (query: string) => Promise<{ value: string; label: string }[]>;
}

export interface DynamicFormProps {
  /** Массив определений полей. */
  fields: FieldDef[];
  /** Начальные значения. */
  initialValues?: Record<string, unknown>;
  /** Callback отправки. */
  onSubmit: (values: Record<string, unknown>) => void;
  /** Текст кнопки отправки. */
  submitLabel?: string;
  /** Форма в состоянии загрузки. */
  loading?: boolean;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function sanitize(value: string): string {
  return value.replace(/[<>]/g, "");
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

/**
 * Динамический рендерер форм на основе массива определений полей.
 *
 * Args:
 *     fields: Массив описаний полей формы.
 *     initialValues: Начальные значения (ключ-значение).
 *     onSubmit: Callback при отправке формы.
 *     submitLabel: Текст на кнопке.
 *     loading: Если true, кнопка отправки неактивна.
 *     className: Дополнительные CSS-классы.
 *
 * Returns:
 *     JSX-элемент динамической формы.
 */
export function DynamicForm({
  fields,
  initialValues = {},
  onSubmit,
  submitLabel = "Save",
  loading = false,
  className,
}: DynamicFormProps) {
  const [values, setValues] = useState<Record<string, unknown>>(() => {
    const init: Record<string, unknown> = {};
    for (const f of fields) {
      init[f.key] = initialValues[f.key] ?? (f.type === "boolean" ? false : "");
    }
    return init;
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [refOptions, setRefOptions] = useState<Record<string, { value: string; label: string }[]>>(
    {},
  );

  useEffect(() => {
    const init: Record<string, unknown> = {};
    for (const f of fields) {
      init[f.key] = initialValues[f.key] ?? (f.type === "boolean" ? false : "");
    }
    setValues(init);
  }, [fields, initialValues]);

  const setValue = useCallback((key: string, value: unknown) => {
    setValues((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => {
      if (!prev[key]) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }, []);

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    for (const f of fields) {
      const v = values[f.key];
      if (f.is_required && (v === "" || v === null || v === undefined)) {
        errs[f.key] = `${f.label} is required`;
      }
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    onSubmit(values);
  };

  const handleRefSearch = useCallback(
    async (field: FieldDef, query: string) => {
      if (!field.loadOptions) return;
      const opts = await field.loadOptions(query);
      setRefOptions((prev) => ({ ...prev, [field.key]: opts }));
    },
    [],
  );

  const inputCls =
    "w-full rounded-lg border border-surface-200 bg-white px-3 py-2 text-sm text-surface-800 placeholder:text-surface-400 focus:outline-none focus:ring-2 focus:ring-primary-400 focus:border-transparent transition-colors disabled:bg-surface-50 disabled:text-surface-400";

  const errorCls = "border-red-300 focus:ring-red-400";

  const renderField = (field: FieldDef) => {
    const val = values[field.key];
    const hasError = !!errors[field.key];

    switch (field.type) {
      case "string":
      case "address":
        return (
          <input
            type="text"
            value={String(val ?? "")}
            placeholder={field.placeholder}
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              setValue(field.key, sanitize(e.target.value))
            }
            className={cn(inputCls, hasError && errorCls)}
          />
        );

      case "integer":
        return (
          <input
            type="number"
            step="1"
            value={val !== "" ? String(val) : ""}
            placeholder={field.placeholder}
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              setValue(field.key, e.target.value === "" ? "" : parseInt(e.target.value, 10))
            }
            className={cn(inputCls, hasError && errorCls)}
          />
        );

      case "decimal":
        return (
          <input
            type="number"
            step="0.01"
            value={val !== "" ? String(val) : ""}
            placeholder={field.placeholder}
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              setValue(field.key, e.target.value === "" ? "" : parseFloat(e.target.value))
            }
            className={cn(inputCls, hasError && errorCls)}
          />
        );

      case "date":
        return (
          <input
            type="date"
            value={String(val ?? "")}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setValue(field.key, e.target.value)}
            className={cn(inputCls, hasError && errorCls)}
          />
        );

      case "boolean":
        return (
          <label className="inline-flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={Boolean(val)}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setValue(field.key, e.target.checked)
              }
              className="h-4 w-4 rounded border-surface-300 text-primary-600 focus:ring-primary-400"
            />
            <span className="text-sm text-surface-600">{field.label}</span>
          </label>
        );

      case "enum":
        return (
          <select
            value={String(val ?? "")}
            onChange={(e: ChangeEvent<HTMLSelectElement>) => setValue(field.key, e.target.value)}
            className={cn(inputCls, hasError && errorCls)}
          >
            <option value="">{field.placeholder ?? "Select..."}</option>
            {field.options?.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        );

      case "reference": {
        const opts = refOptions[field.key] ?? [];
        return (
          <div className="relative">
            <input
              type="text"
              placeholder={field.placeholder ?? "Search..."}
              onChange={(e: ChangeEvent<HTMLInputElement>) => {
                const q = sanitize(e.target.value);
                handleRefSearch(field, q);
              }}
              className={cn(inputCls, hasError && errorCls)}
            />
            {opts.length > 0 && (
              <ul className="absolute z-10 mt-1 max-h-40 w-full overflow-y-auto rounded-lg border border-surface-200 bg-white shadow-lg">
                {opts.map((opt) => (
                  <li key={opt.value}>
                    <button
                      type="button"
                      className="w-full px-3 py-2 text-left text-sm text-surface-700 hover:bg-primary-50 transition-colors"
                      onClick={() => {
                        setValue(field.key, opt.value);
                        setRefOptions((prev) => ({ ...prev, [field.key]: [] }));
                      }}
                    >
                      {opt.label}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {val != null && (
              <p className="mt-1 text-xs text-surface-400">
                Selected: {String(val) as string}
              </p>
            )}
          </div>
        );
      }

      default:
        return null;
    }
  };

  return (
    <form onSubmit={handleSubmit} className={cn("space-y-4", className)}>
      {fields.map((field) => (
        <div key={field.key}>
          {field.type !== "boolean" && (
            <label className="mb-1.5 block text-sm font-medium text-surface-700">
              {field.label}
              {field.is_required && <span className="ml-0.5 text-red-500">*</span>}
            </label>
          )}
          {renderField(field)}
          {errors[field.key] && (
            <p className="mt-1 text-xs text-red-500">{errors[field.key]}</p>
          )}
        </div>
      ))}

      <button
        type="submit"
        disabled={loading}
        className={cn(
          "w-full rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-medium text-white transition-colors",
          "hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-400 focus:ring-offset-2",
          "disabled:opacity-50 disabled:cursor-not-allowed",
        )}
      >
        {loading ? "Saving..." : submitLabel}
      </button>
    </form>
  );
}

export default DynamicForm;
