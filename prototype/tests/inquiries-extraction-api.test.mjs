import assert from "node:assert/strict";
import test from "node:test";
import { inquiryApi } from "../src/api/inquiries.js";

test("extraction reads use the latest, history, and individual record API routes", async t => {
  const originalFetch = globalThis.fetch;
  const requests = [];
  globalThis.fetch = async (url, options = {}) => {
    requests.push({ url: String(url), method: options.method || "GET" });
    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  t.after(() => {
    globalThis.fetch = originalFetch;
  });

  await inquiryApi.latestExtraction("inq-1");
  await inquiryApi.extractionHistory("inq-1");
  await inquiryApi.extraction("inq-1", "ext-2");

  assert.deepEqual(requests, [
    { url: "http://localhost:8010/api/v1/inquiries/inq-1/extractions/latest", method: "GET" },
    { url: "http://localhost:8010/api/v1/inquiries/inq-1/extractions", method: "GET" },
    { url: "http://localhost:8010/api/v1/inquiries/inq-1/extractions/ext-2", method: "GET" },
  ]);
});
