export type NotificationLinkPayload = {
  document_id?: string | null;
  thread_id?: string | null;
  panel?: string | null;
};

export type NotificationRouter = { push: (href: string) => void };

export function navigateFromNotificationLink(router: NotificationRouter, link: NotificationLinkPayload): void {
  const panel = link.panel === "documents" ? "documents" : "query";
  const path = panel === "documents" ? "/documents" : "/query";
  const qs = new URLSearchParams();
  const doc = link.document_id?.trim();
  const tid = link.thread_id?.trim();
  if (doc) qs.set("document", doc);
  if (tid) qs.set("thread", tid);
  const suffix = qs.toString();
  router.push(suffix ? `${path}?${suffix}` : path);
}
