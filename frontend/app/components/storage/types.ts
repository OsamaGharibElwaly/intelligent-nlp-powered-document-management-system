export type StorageDoc = {
  document_id: string;
  owner_id?: string;
  collection_id: string;
  filename: string;
  file_size?: number;
  active_version?: number;
  tags?: string[];
  metadata?: Record<string, string>;
  versions?: Array<{ version: number; file_size: number }>;
  read_status?: "unread" | "reading" | "completed";
  last_read_at?: string | null;
  reading_progress?: number;
  priority?: "low" | "medium" | "high";
  due_date?: string | null;
  pinned?: boolean;
  archived?: boolean;
};

export type StorageFilterId = "unread" | "in_progress" | "completed" | "overdue" | "pinned" | "archived";
