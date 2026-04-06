/**
 * WebSocket client for real-time updates from the HVAC CRM backend.
 *
 * Клиент WebSocket для получения real-time обновлений (задачи, уведомления,
 * статусы пользователей). Поддерживает автоматическое переподключение
 * с экспоненциальным back-off и типизированные события.
 */

import type { WsMessage } from "@/types";

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";

const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;
const HEARTBEAT_INTERVAL_MS = 30000;

type EventHandler<T = unknown> = (data: T) => void;
type ConnectionHandler = () => void;

/**
 * Resilient WebSocket wrapper with auto-reconnect, heartbeat and typed events.
 *
 * Обёртка над нативным WebSocket с поддержкой:
 * - Авторизации через токен в query-параметре.
 * - Автоматического переподключения при обрыве связи.
 * - Экспоненциального back-off для задержки между попытками.
 * - Heartbeat-пингов для поддержания соединения.
 * - Подписки/отписки на типизированные события.
 */
export class WsClient {
  private socket: WebSocket | null = null;
  private token: string | null = null;
  private listeners = new Map<string, Set<EventHandler>>();
  private connectHandlers = new Set<ConnectionHandler>();
  private disconnectHandlers = new Set<ConnectionHandler>();
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private intentionallyClosed = false;

  /**
   * Set auth token and (re)connect.
   *
   * Устанавливает токен авторизации. Если соединение уже открыто — переподключает.
   *
   * Args:
   *   token: JWT access-токен.
   */
  setToken(token: string): void {
    this.token = token;
    if (this.socket) {
      this.disconnect();
      this.connect();
    }
  }

  /**
   * Open a WebSocket connection to the backend.
   *
   * Открывает WebSocket-соединение, передавая токен в query-параметре.
   */
  connect(): void {
    if (this.socket?.readyState === WebSocket.OPEN) return;
    if (typeof window === "undefined") return;

    this.intentionallyClosed = false;
    const url = this.token ? `${WS_BASE}?token=${this.token}` : WS_BASE;

    try {
      this.socket = new WebSocket(url);
    } catch {
      this.scheduleReconnect();
      return;
    }

    this.socket.onopen = () => {
      this.reconnectAttempts = 0;
      this.startHeartbeat();
      this.connectHandlers.forEach((h) => h());
    };

    this.socket.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        const handlers = this.listeners.get(msg.event);
        handlers?.forEach((h) => h(msg.data));
      } catch {
        /* ignore malformed frames */
      }
    };

    this.socket.onclose = () => {
      this.stopHeartbeat();
      this.disconnectHandlers.forEach((h) => h());
      if (!this.intentionallyClosed) {
        this.scheduleReconnect();
      }
    };

    this.socket.onerror = () => {
      this.socket?.close();
    };
  }

  /**
   * Gracefully close the connection without auto-reconnect.
   *
   * Закрывает соединение без автоматического переподключения.
   */
  disconnect(): void {
    this.intentionallyClosed = true;
    this.clearReconnectTimer();
    this.stopHeartbeat();
    this.socket?.close();
    this.socket = null;
  }

  /**
   * Subscribe to a specific event type.
   *
   * Подписывает обработчик на события определённого типа.
   *
   * Args:
   *   event: Имя события (например, "task.updated").
   *   handler: Функция-обработчик, вызываемая при получении события.
   *
   * Returns:
   *   Функция отписки.
   */
  on<T = unknown>(event: string, handler: EventHandler<T>): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    const set = this.listeners.get(event)!;
    set.add(handler as EventHandler);

    return () => {
      set.delete(handler as EventHandler);
      if (set.size === 0) this.listeners.delete(event);
    };
  }

  /**
   * Register a handler called when connection opens.
   *
   * Регистрирует обработчик, вызываемый при установлении соединения.
   */
  onConnect(handler: ConnectionHandler): () => void {
    this.connectHandlers.add(handler);
    return () => this.connectHandlers.delete(handler);
  }

  /**
   * Register a handler called when connection closes.
   *
   * Регистрирует обработчик, вызываемый при закрытии соединения.
   */
  onDisconnect(handler: ConnectionHandler): () => void {
    this.disconnectHandlers.add(handler);
    return () => this.disconnectHandlers.delete(handler);
  }

  /**
   * Send a JSON message through the socket.
   *
   * Отправляет JSON-сообщение через WebSocket.
   *
   * Args:
   *   event: Имя события.
   *   data: Данные для отправки.
   */
  send(event: string, data: unknown): void {
    if (this.socket?.readyState !== WebSocket.OPEN) return;
    this.socket.send(JSON.stringify({ event, data }));
  }

  get isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  private scheduleReconnect(): void {
    this.clearReconnectTimer();
    const delay = Math.min(
      RECONNECT_BASE_MS * 2 ** this.reconnectAttempts,
      RECONNECT_MAX_MS,
    );
    this.reconnectAttempts++;
    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      this.send("ping", {});
    }, HEARTBEAT_INTERVAL_MS);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }
}

export const ws = new WsClient();
