export interface Connection {
  url: string;
  username: string;
  password?: string;
  password_configured?: boolean;
  api_key?: string;
  api_key_configured?: boolean;
  timeout: number;
}
export interface Rules {
  feeds: string[];
  min_gib: number;
  max_gib: number;
  max_count: number;
  reserve_gib: number;
  replacement: "seed_time" | "added_time";
  age_hours: number;
  title_pattern: string;
}
export interface Schedule {
  enabled: boolean;
  mode: "interval" | "cron";
  interval_seconds: number;
  cron: string;
  timezone: string;
}
export interface Match {
  text: string;
  regex: boolean;
}
export interface Attendance {
  id?: string;
  name: string;
  enabled: boolean;
  url: string;
  method: "GET" | "POST";
  headers?: Record<string, string>;
  cookie?: string;
  body?: string;
  cookie_configured?: boolean;
  headers_configured?: boolean;
  body_configured?: boolean;
  time: string;
  success: Match;
  already: Match;
  expired: Match;
}
export interface Notifications {
  webhook_enabled: boolean;
  webhook_url?: string;
  webhook_url_configured?: boolean;
  webhook_method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  webhook_headers?: Record<string, string>;
  webhook_headers_configured?: boolean;
  webhook_format: "json" | "form" | "text";
  webhook_body?: string;
  webhook_body_configured?: boolean;
  webhook_timeout: number;
  smtp_enabled: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_security: "ssl" | "starttls";
  smtp_username: string;
  smtp_password?: string;
  smtp_password_configured?: boolean;
  smtp_from: string;
  smtp_to: string[];
  events: string[];
}
export interface Settings {
  connection: Connection;
  rules: Rules;
  schedule: Schedule;
  attendance: Attendance[];
  notifications: Notifications;
}
export interface PlanItem {
  key: string;
  title: string;
  feed: string;
  size: number | null;
  action: string;
  reason: string;
  delete?: { hash: string; name: string };
}
export interface Plan {
  managed_count: number;
  total_count: number;
  free_bytes: number | null;
  disk_warning: string;
  items: PlanItem[];
}
export interface Action {
  title: string;
  action: string;
  status: string;
  reason?: string;
  warning?: string;
  deleted_hash?: string;
}
export interface Notice {
  channel: string;
  status: string;
  reason?: string;
}
export interface Run {
  id: number;
  kind: string;
  started: number;
  finished: number | null;
  status: string;
  detail: {
    name?: string;
    reason?: string;
    error?: string;
    plan?: Plan;
    actions?: Action[];
    notifications?: Notice[];
  };
}
export interface Pending {
  key: string;
  hash: string;
  state: string;
}
export interface Dashboard {
  connected: boolean;
  error?: string;
  version?: string;
  free_bytes?: number;
  managed_count?: number;
  total_count?: number;
  schedule_enabled: boolean;
  jobs: { id: string; next_run: string | null }[];
  recent: Run[];
  pending: Pending[];
}
export interface Torrent {
  hash: string;
  name: string;
  size: number;
  total_size: number;
  progress: number;
  state: string;
  added_on: number;
  seeding_time: number | null;
  tags: string;
  managed: boolean;
}

export interface SettingsPageProps {
  settings: Settings;
  update: <K extends keyof Settings>(key: K, value: Settings[K]) => void;
  save: (key: keyof Settings) => Promise<void>;
  busy: boolean;
  action: (work: () => Promise<void>, success?: string) => Promise<void>;
  setMessage: (message: string) => void;
}
