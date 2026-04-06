/**
 * Shared TypeScript type definitions for the HVAC CRM frontend.
 *
 * Все интерфейсы синхронизированы с Pydantic-схемами бэкенда.
 * Используются как единственный источник правды для типизации
 * API-ответов и компонентов UI.
 */

/* ------------------------------------------------------------------ */
/*  Common / Pagination                                                */
/* ------------------------------------------------------------------ */

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}

/* ------------------------------------------------------------------ */
/*  Auth / User                                                        */
/* ------------------------------------------------------------------ */

export type UserRole =
  | "admin"
  | "manager"
  | "engineer"
  | "dispatcher"
  | "warehouse_keeper"
  | "accountant";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  avatar_url?: string;
  phone?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

/* ------------------------------------------------------------------ */
/*  Notifications                                                      */
/* ------------------------------------------------------------------ */

export type NotificationType =
  | "task_assigned"
  | "task_updated"
  | "deal_stage_changed"
  | "tender_deadline"
  | "low_stock"
  | "equipment_service"
  | "comment_mention"
  | "system";

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  is_read: boolean;
  entity_type?: string;
  entity_id?: string;
  created_at: string;
}

/* ------------------------------------------------------------------ */
/*  WebSocket Events                                                   */
/* ------------------------------------------------------------------ */

export interface WsMessage<T = unknown> {
  event: string;
  data: T;
  timestamp: string;
}

/* ------------------------------------------------------------------ */
/*  User                                                               */
/* ------------------------------------------------------------------ */

export interface UserSummary {
  id: string;
  full_name: string;
  email: string;
  role: string;
}

/* ------------------------------------------------------------------ */
/*  Task                                                               */
/* ------------------------------------------------------------------ */

export type Priority = "low" | "medium" | "high" | "critical";

export type TaskStatus =
  | "new"
  | "dispatched"
  | "in_progress"
  | "testing"
  | "photo_report"
  | "act_signing"
  | "done"
  | "completed"
  | "closed";

export interface TemplateSummary {
  id: string;
  name: string;
  category: string;
}

export interface TaskResponse {
  id: string;
  template_id: string | null;
  board_id: string | null;
  client_id: string | null;
  deal_id: string | null;
  tender_id: string | null;
  assigned_to: string | null;
  created_by: string | null;
  title: string;
  description: string | null;
  status: string;
  priority: Priority;
  custom_fields: Record<string, unknown>;
  due_date: string | null;
  started_at: string | null;
  completed_at: string | null;
  sla_deadline: string | null;
  assignee: UserSummary | null;
  template: TemplateSummary | null;
  created_at: string;
  updated_at: string;
}

export interface ChecklistItemResponse {
  id: string;
  title: string;
  is_completed: boolean;
  completed_by: string | null;
  completed_at: string | null;
  order: number;
}

export interface ChecklistResponse {
  id: string;
  title: string;
  gate_transition: string | null;
  is_completed: boolean;
  items: ChecklistItemResponse[];
}

export interface CommentResponse {
  id: string;
  author_id: string;
  author_name: string | null;
  body: string;
  mentions: unknown[];
  attachments: unknown[];
  created_at: string;
}

export interface DocumentResponse {
  id: string;
  doc_type: string;
  label: string | null;
  filename: string;
  mime_type: string;
  file_size: number;
  version: number;
  uploaded_by: string;
  created_at: string;
}

export interface TimeEntryBrief {
  id: string;
  user_id: string;
  started_at: string | null;
  ended_at: string | null;
  duration_minutes: number;
  entry_type: string;
  is_billable: boolean;
  notes: string | null;
}

export interface StatusHistoryResponse {
  id: string;
  from_status: string;
  to_status: string;
  changed_by: string;
  reason: string | null;
  transition_data: Record<string, unknown>;
  created_at: string;
}

export interface TaskDetail extends TaskResponse {
  checklists: ChecklistResponse[];
  comments: CommentResponse[];
  documents: DocumentResponse[];
  time_entries: TimeEntryBrief[];
  status_history: StatusHistoryResponse[];
}

/* ------------------------------------------------------------------ */
/*  Client                                                             */
/* ------------------------------------------------------------------ */

export interface ClientContactResponse {
  id: string;
  client_id: string;
  full_name: string;
  position: string | null;
  phone: string | null;
  email: string | null;
  is_primary: boolean;
  created_at: string;
  updated_at: string;
}

export interface ClientResponse {
  id: string;
  name: string;
  client_type: string;
  address: string | null;
  phone: string | null;
  email: string | null;
  inn: string | null;
  coordinates: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
  notes: string | null;
  contacts: ClientContactResponse[];
  created_at: string;
  updated_at: string;
}

/* ------------------------------------------------------------------ */
/*  Deal                                                               */
/* ------------------------------------------------------------------ */

export interface DealStageResponse {
  id: string;
  name: string;
  order: number;
  color: string;
  is_won: boolean;
  is_lost: boolean;
  created_at: string;
  updated_at: string;
}

export interface DealResponse {
  id: string;
  client_id: string;
  title: string;
  description: string | null;
  amount: number;
  stage_id: string;
  assigned_to: string | null;
  expected_close: string | null;
  source: string | null;
  created_at: string;
  updated_at: string;
}

/* ------------------------------------------------------------------ */
/*  Tender                                                             */
/* ------------------------------------------------------------------ */

export type TenderStatus =
  | "search"
  | "participation"
  | "won"
  | "execution"
  | "completed"
  | "lost";

export interface TenderResponse {
  id: string;
  title: string;
  description: string | null;
  source: string | null;
  budget: number | null;
  our_price: number | null;
  status: TenderStatus;
  deadline: string | null;
  execution_deadline: string | null;
  assigned_to: string | null;
  requirements: Record<string, unknown>;
  documents_url: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

/* ------------------------------------------------------------------ */
/*  Time Entry                                                         */
/* ------------------------------------------------------------------ */

export interface TimeEntryResponse {
  id: string;
  task_id: string;
  user_id: string;
  started_at: string | null;
  ended_at: string | null;
  duration_minutes: number;
  entry_type: string;
  is_billable: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface TimeSummary {
  total_minutes: number;
  total_hours: number;
  entries_count: number;
  period: { from: string | null; to: string | null };
}

/* ------------------------------------------------------------------ */
/*  Warehouse                                                          */
/* ------------------------------------------------------------------ */

export interface WarehouseItemResponse {
  id: string;
  name: string;
  sku: string;
  category: string;
  unit: string;
  quantity: number;
  reserved_quantity: number;
  min_quantity: number;
  price: number;
  description: string | null;
  location: string | null;
  created_at: string;
  updated_at: string;
}

export interface WarehouseMovementResponse {
  id: string;
  item_id: string;
  task_id: string | null;
  user_id: string;
  movement_type: string;
  quantity: number;
  unit_price: number | null;
  reason: string | null;
  destination: string | null;
  created_at: string;
  updated_at: string;
}

/* ------------------------------------------------------------------ */
/*  Equipment                                                          */
/* ------------------------------------------------------------------ */

export type EquipmentStatus = "active" | "maintenance" | "written_off" | "lost";

export interface EquipmentResponse {
  id: string;
  name: string;
  serial_number: string;
  category: string;
  purchase_price: number;
  purchase_date: string;
  service_life_months: number;
  current_value: number;
  status: EquipmentStatus;
  assigned_to: string | null;
  location: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

/* ------------------------------------------------------------------ */
/*  Template                                                           */
/* ------------------------------------------------------------------ */

export interface TemplateStageResponse {
  id: string;
  name: string;
  status_id: string;
  order: number;
  description: string | null;
}

export interface TemplateChecklistResponse {
  id: string;
  checklist_id: string;
  title: string;
  gate_transition: string | null;
  items: unknown[];
}

export interface TemplateFieldResponse {
  id: string;
  key: string;
  label: string;
  field_type: string;
  is_required: boolean;
  options: unknown[] | null;
  default_value: string | null;
  order: number;
}

export interface TemplateResponse {
  id: string;
  name: string;
  category: string;
  description: string | null;
  workflow_definition: Record<string, unknown>;
  required_fields: unknown[];
  sla_config: Record<string, unknown>;
  auto_warehouse: unknown[];
  required_documents: Record<string, unknown>;
  is_active: boolean;
  stages: TemplateStageResponse[];
  checklists: TemplateChecklistResponse[];
  fields: TemplateFieldResponse[];
  created_at: string;
  updated_at: string;
}

/* ------------------------------------------------------------------ */
/*  Reference                                                          */
/* ------------------------------------------------------------------ */

export interface ReferenceItemResponse {
  id: string;
  reference_id: string;
  code: string;
  name: string;
  metadata: Record<string, unknown>;
  order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ReferenceResponse {
  id: string;
  code: string;
  name: string;
  description: string | null;
  is_system: boolean;
  items: ReferenceItemResponse[];
  created_at: string;
  updated_at: string;
}

/* ------------------------------------------------------------------ */
/*  Analytics                                                          */
/* ------------------------------------------------------------------ */

export interface DashboardStats {
  total_tasks: number;
  tasks_by_status: Record<string, number>;
  overdue_tasks: number;
  total_deals: number;
  deals_amount: number;
  active_tenders: number;
  low_stock_items: number;
}

export interface PerformanceStats {
  user_id: string;
  tasks_completed: number;
  tasks_in_progress: number;
  avg_completion_hours: number;
  total_hours_logged: number;
  on_time_rate: number;
}

export interface TenderAnalytics {
  total_tenders: number;
  tenders_by_status: Record<string, number>;
  win_rate: number;
  total_budget: number;
  total_our_price: number;
}

export interface WarehouseAnalytics {
  total_items: number;
  low_stock_items: Array<{
    id: string;
    name: string;
    sku: string;
    quantity: number;
    min_quantity: number;
  }>;
  total_value: number;
  movements_summary: Record<
    string,
    { count: number; total_quantity: number }
  >;
}

/* ------------------------------------------------------------------ */
/*  Board                                                              */
/* ------------------------------------------------------------------ */

export interface BoardResponse {
  id: string;
  name: string;
  description: string | null;
  board_type: string;
  owner_id: string | null;
  columns: unknown[];
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}
