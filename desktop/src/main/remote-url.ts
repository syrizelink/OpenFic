const NGROK_DOMAINS = [
  "ngrok-free.app",
  "ngrok-free.dev",
  "ngrok.app",
  "ngrok.dev",
  "ngrok.pizza",
  "ngrok.io",
];

export function isNgrokUrl(value: string): boolean {
  try {
    const { protocol, hostname, username, password } = new URL(value);
    return (
      (protocol === "http:" || protocol === "https:") &&
      !username &&
      !password &&
      NGROK_DOMAINS.some((domain) => hostname === domain || hostname.endsWith(`.${domain}`))
    );
  } catch {
    return false;
  }
}
