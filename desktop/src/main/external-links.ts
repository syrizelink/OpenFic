type ExternalLinkEvent = {
  preventDefault: () => void;
};

type ExternalLinkContents = {
  on: (event: "will-navigate", listener: (event: ExternalLinkEvent, url: string) => void) => void;
  setWindowOpenHandler: (handler: (details: { url: string }) => { action: "deny" }) => void;
};

type OpenExternal = (url: string) => Promise<void>;

function isExternalWebUrl(value: string): boolean {
  try {
    const protocol = new URL(value).protocol;
    return protocol === "http:" || protocol === "https:";
  } catch {
    return false;
  }
}

export function attachExternalLinkHandlers(contents: ExternalLinkContents, openExternal: OpenExternal): void {
  const openExternalUrl = (url: string): void => {
    if (isExternalWebUrl(url)) void openExternal(url);
  };

  contents.setWindowOpenHandler(({ url }) => {
    openExternalUrl(url);
    return { action: "deny" };
  });

  contents.on("will-navigate", (event, url) => {
    if (!isExternalWebUrl(url)) return;
    event.preventDefault();
    openExternalUrl(url);
  });
}
