/**
 * Canonical equipment category keys and Russian labels for UI selects.
 *
 * Keys are stored as ``Equipment.category`` in the API (free-form string with length cap).
 */

const EQUIPMENT_CATEGORY_ROWS = [
  ["crew", "Бригада / подряд (почасовая)"],
  ["automobile", "Автомобили"],
  ["vehicle", "Транспорт"],
  ["instrument", "Инструмент"],
  ["power_tool", "Электроинструмент"],
  ["hand_tool", "Ручной инструмент"],
  ["measuring", "Измерительное"],
  ["safety", "Безопасность"],
] as const;

export const EQUIPMENT_CATEGORY_LABELS: Record<string, string> = Object.fromEntries(
  EQUIPMENT_CATEGORY_ROWS,
) as Record<string, string>;

/** Stable order for selects and filter dropdowns. */
export const EQUIPMENT_CATEGORY_KEYS: readonly string[] = EQUIPMENT_CATEGORY_ROWS.map((r) => r[0]);

/** Categories that require mileage (km) in field-work tasks, same as legacy ``vehicle``. */
export function isMileageEquipmentCategory(category: string | null | undefined): boolean {
  const c = (category ?? "").trim().toLowerCase();
  return c === "vehicle" || c === "automobile";
}
