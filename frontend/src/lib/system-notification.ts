export function showSystemNotification(title: string, body: string): void {
  new Notification(title, { body, icon: "/pwa-icons/icon-192.png" });
}
