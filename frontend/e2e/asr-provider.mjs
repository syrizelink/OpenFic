// A real HTTP upstream for ASR integration tests; no production API is mocked.
import { createServer } from "node:http";

let behavior = { status: 200, text: "语音转写测试。", delay: 0 };
let calls = 0;
createServer(async (request, response) => {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  const body = Buffer.concat(chunks);
  response.setHeader("Content-Type", "application/json");
  if (request.url === "/health") return response.end("{}");
  if (request.url === "/control") {
    if (request.method === "POST") {
      behavior = { status: 200, text: "语音转写测试。", delay: 0, ...JSON.parse(body) };
      calls = 0;
    }
    return response.end(JSON.stringify({ ...behavior, calls }));
  }
  calls++;
  const start = body.indexOf("RIFF");
  if (
    request.headers.authorization !== "Bearer e2e-secret" ||
    start < 0 ||
    body.toString("ascii", start + 8, start + 12) !== "WAVE" ||
    body.readUInt32LE(start + 24) !== 16000 ||
    body.readUInt16LE(start + 22) !== 1
  ) {
    response.statusCode = 400;
    return response.end(JSON.stringify({ error: "Invalid authentication or canonical WAV" }));
  }
  await new Promise((resolve) => setTimeout(resolve, behavior.delay));
  response.statusCode = behavior.status;
  response.end(JSON.stringify({ text: behavior.text }));
}).listen(18888, "127.0.0.1");
