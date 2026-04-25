/**
 * Kanban column metadata for the field-work board (matches ``/field-work`` column IDs / task statuses).
 * Stored on ``Board.columns`` for reference and future board UIs.
 */
export const FIELD_WORK_BOARD_COLUMNS: Array<{
  id: string;
  title: string;
  task_status: string;
  color: string;
}> = [
  { id: "new", title: "Новая", task_status: "new", color: "#94a3b8" },
  { id: "dispatched", title: "Назначена", task_status: "dispatched", color: "#38bdf8" },
  { id: "in_progress", title: "В работе", task_status: "in_progress", color: "#3b82f6" },
  { id: "testing", title: "Согласование", task_status: "testing", color: "#fbbf24" },
  { id: "done", title: "Выполнено", task_status: "done", color: "#22c55e" },
];
