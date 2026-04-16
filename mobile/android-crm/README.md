# SPEC CRM — Android client

Native **Kotlin + Jetpack Compose** app that talks to the same backend as the web CRM (`/api/v1`).

## Features

- Login via `POST /auth/login` (Keycloak or dev bypass — same as web).
- Stores access/refresh tokens, active company id, and API base URL in **DataStore**.
- Sends `Authorization: Bearer` and `X-Company-Id` on requests (same as the browser).
- **Token refresh** on HTTP 401 (`/auth/refresh`).
- **Navigation drawer** with the same main sections as the web sidebar: Главная, Задачи, Шаблоны, Клиенты, Сделки, Тендеры, Чат, AI, Учёт времени, Склад, Оборудование, Аналитика, Уведомления, Профиль, Настройки (справочники), Пользователи, Роли, Админка (для `admin`).
- **Multi-company**: `GET /companies/mine` in the drawer; switching updates `X-Company-Id`.
- **Screens** call the same REST API as the Next.js app (`/api/v1/...`): dashboard stats, task list + detail + status transition, clients (search), deals + stages, tenders list + detail, templates, chat, AI assistant (text chat), time entries + summary, warehouse items, equipment list, analytics, notifications list, profile edit, users list, admin/deploy + scheduler summary (read-only), roles matrix (reference).

Some web-only flows (full tender pipeline editor, document upload, Kanban/calendar views, Excel import/export, deploy trigger) are **not** replicated one-to-one; extend the app using the same `CrmApi` / `CrmRepository` patterns.

## Open in Android Studio

1. **File → Open** → select the folder `mobile/android-crm`.
2. Let Gradle sync; if prompted, install **Android SDK 34** and a recent **JDK 17**.
3. Run on an emulator or device (**Run** ▶).

If the Gradle wrapper is missing, Android Studio can create it, or install Gradle and run `gradle wrapper` in this directory.

## API base URL

The login screen **Адрес API** must reach the same API the web app uses (including `/api/v1` path — the app adds it if you omit it).

Examples:

| Environment | Example |
|-------------|---------|
| Web CRM at `http://SERVER:9000` | `http://SERVER:9000` |
| Android emulator, backend on host port 9000 | `http://10.0.2.2:9000` (default in code) |
| HTTPS reverse proxy | `https://crm.example.com` |

Use the **LAN IP** of your PC when testing on a physical device (not `localhost`).

## Security

- Debug build allows **cleartext HTTP** (`networkSecurityConfig` + manifest flags) for local/LAN installs.
- For production, serve **HTTPS** and tighten `network_security_config` / remove `usesCleartextTraffic`.

## Next steps (ideas)

- Tender transitions, document upload, task create/edit forms.
- Offline cache, push notifications (FCM).
