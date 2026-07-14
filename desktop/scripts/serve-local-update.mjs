import { createReadStream, existsSync } from "node:fs";
import { stat } from "node:fs/promises";
import { createServer } from "node:http";
import path from "node:path";

const port = Number(process.env.OPENFIC_UPDATE_PORT ?? "4567");
const updateDirectory = path.resolve(process.argv[2] ?? "dist-electron");
const contentTypes = new Map([
  [".exe", "application/vnd.microsoft.portable-executable"],
  [".yml", "text/yaml; charset=utf-8"],
  [".blockmap", "application/octet-stream"],
]);

if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error("OPENFIC_UPDATE_PORT must be an integer between 1 and 65535.");
}

if (!existsSync(updateDirectory)) {
  throw new Error(`Update directory does not exist: ${updateDirectory}`);
}

function resolveRequestPath(requestUrl) {
  const pathname = decodeURIComponent(new URL(requestUrl ?? "/", "http://localhost").pathname);
  const filePath = path.resolve(updateDirectory, `.${pathname}`);
  if (filePath !== updateDirectory && !filePath.startsWith(`${updateDirectory}${path.sep}`)) return null;
  return filePath;
}

function getByteRange(rangeHeader, size) {
  if (!rangeHeader) return { start: 0, end: size - 1, partial: false };
  const match = /^bytes=(\d*)-(\d*)$/.exec(rangeHeader);
  if (!match) return null;

  const [, startText, endText] = match;
  if (!startText && !endText) return null;
  if (!startText) {
    const suffixLength = Number(endText);
    if (!Number.isSafeInteger(suffixLength) || suffixLength < 1) return null;
    return { start: Math.max(0, size - suffixLength), end: size - 1, partial: true };
  }

  const start = Number(startText);
  const end = endText ? Number(endText) : size - 1;
  if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start > end || start >= size) return null;
  return { start, end: Math.min(end, size - 1), partial: true };
}

const server = createServer(async (request, response) => {
  if (request.method !== "GET" && request.method !== "HEAD") {
    response.writeHead(405, { Allow: "GET, HEAD" });
    response.end();
    return;
  }

  let filePath;
  try {
    filePath = resolveRequestPath(request.url);
  } catch {
    response.writeHead(400);
    response.end();
    return;
  }

  if (!filePath) {
    response.writeHead(403);
    response.end();
    return;
  }

  try {
    const fileInfo = await stat(filePath);
    if (!fileInfo.isFile()) throw new Error("Not a file");
    const byteRange = getByteRange(request.headers.range, fileInfo.size);
    if (!byteRange) {
      response.writeHead(416, { "Content-Range": `bytes */${fileInfo.size}` });
      response.end();
      return;
    }

    response.writeHead(byteRange.partial ? 206 : 200, {
      "Accept-Ranges": "bytes",
      "Content-Length": byteRange.end - byteRange.start + 1,
      "Content-Type": contentTypes.get(path.extname(filePath)) ?? "application/octet-stream",
      "Cache-Control": "no-store",
      ...(byteRange.partial ? { "Content-Range": `bytes ${byteRange.start}-${byteRange.end}/${fileInfo.size}` } : {}),
    });
    if (request.method === "HEAD") {
      response.end();
      return;
    }
    createReadStream(filePath, { start: byteRange.start, end: byteRange.end }).pipe(response);
  } catch {
    response.writeHead(404);
    response.end();
  }
});

server.listen(port, "127.0.0.1", () => {
  console.log(`Serving local update files from ${updateDirectory}`);
  console.log(`Update URL: http://127.0.0.1:${port}`);
});
