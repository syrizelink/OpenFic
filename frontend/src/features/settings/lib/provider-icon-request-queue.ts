const MAX_CONCURRENT_PROVIDER_ICON_REQUESTS = 2;

const pendingRequests: Array<() => void> = [];
let activeRequestCount = 0;

export function scheduleProviderIconRequest(request: () => Promise<void>): () => void {
  let hasStarted = false;
  let isCancelled = false;

  const start = () => {
    hasStarted = true;
    if (isCancelled) {
      startPendingRequests();
      return;
    }

    activeRequestCount += 1;
    void request().finally(() => {
      activeRequestCount -= 1;
      startPendingRequests();
    });
  };

  pendingRequests.push(start);
  startPendingRequests();

  return () => {
    isCancelled = true;
    if (!hasStarted) {
      const index = pendingRequests.indexOf(start);
      if (index >= 0) pendingRequests.splice(index, 1);
    }
  };
}

function startPendingRequests(): void {
  while (activeRequestCount < MAX_CONCURRENT_PROVIDER_ICON_REQUESTS) {
    const request = pendingRequests.shift();
    if (!request) return;
    request();
  }
}
