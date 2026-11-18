import assert from "node:assert/strict";
import test from "node:test";
import { loadExtractionState, prependExtraction } from "../src/extractionState.js";

const record = (extraction_id, inquiry_id, extraction_status, error_code = null) => ({
  extraction_id,
  inquiry_id,
  extraction_status,
  error_code,
  created_at: "2026-11-18T05:00:00+00:00",
});

test("restores the latest extraction and all history when an inquiry is loaded", async () => {
  const latest = record("success-2", "inquiry-a", "SUCCESS");
  const failed = record("failed-1", "inquiry-a", "FAILED", "PROVIDER_TIMEOUT");
  const calls = [];
  const api = {
    latestExtraction: async id => {
      calls.push(["latest", id]);
      return latest;
    },
    extractionHistory: async id => {
      calls.push(["history", id]);
      return { items: [latest, failed], total: 2 };
    },
  };

  const state = await loadExtractionState(api, "inquiry-a");

  assert.deepEqual(state, { latest, history: [latest, failed] });
  assert.deepEqual(calls, [["latest", "inquiry-a"], ["history", "inquiry-a"]]);
});

test("switching inquiries and reloading restores each inquiry's newest result, including failures", async () => {
  const initial = record("a-1", "inquiry-a", "SUCCESS");
  const failed = record("b-1", "inquiry-b", "FAILED", "UNAVAILABLE");
  let latestForA = initial;
  const api = {
    latestExtraction: async id => id === "inquiry-a" ? latestForA : failed,
    extractionHistory: async id => ({
      items: id === "inquiry-a" && latestForA.extraction_id === "a-2" ? [] : [id === "inquiry-a" ? latestForA : failed],
      total: 1,
    }),
  };

  assert.equal((await loadExtractionState(api, "inquiry-a")).latest.extraction_id, "a-1");
  const switched = await loadExtractionState(api, "inquiry-b");
  assert.equal(switched.latest.extraction_status, "FAILED");
  assert.equal(switched.latest.error_code, "UNAVAILABLE");

  latestForA = record("a-2", "inquiry-a", "SUCCESS");
  const refreshed = await loadExtractionState(api, "inquiry-a");
  assert.equal(refreshed.latest.extraction_id, "a-2");
  assert.deepEqual(refreshed.history.map(item => item.extraction_id), ["a-2"]);
});

test("a retry prepends a new record without replacing any earlier success or failure", () => {
  const earlier = record("old-1", "inquiry-a", "FAILED", "PROVIDER_TIMEOUT");
  const retry = {...record("new-2", "inquiry-a", "SUCCESS"), created_at: "2026-11-18T05:00:00.000001+00:00"};
  const history = prependExtraction([earlier], retry);

  assert.deepEqual(history, [retry, earlier]);
  assert.deepEqual(prependExtraction(history, retry), [retry, earlier]);
});

test("an inquiry without extraction restores an empty state", async () => {
  const state = await loadExtractionState({
    latestExtraction: async () => null,
    extractionHistory: async () => ({ items: [], total: 0 }),
  }, "inquiry-new");

  assert.deepEqual(state, { latest: null, history: [] });
});


test("resolves a concurrent retry race in favor of the newest history item", async () => {
  const staleLatest = record("record-1", "inquiry-a", "SUCCESS");
  const concurrentRetry = {
    ...record("record-2", "inquiry-a", "FAILED", "UNAVAILABLE"),
    created_at: "2026-11-18T05:01:00+00:00",
  };
  const state = await loadExtractionState({
    latestExtraction: async () => staleLatest,
    extractionHistory: async () => ({ items: [concurrentRetry, staleLatest], total: 2 }),
  }, "inquiry-a");

  assert.equal(state.latest.extraction_id, "record-2");
  assert.deepEqual(state.history.map(item => item.extraction_id), ["record-2", "record-1"]);
});


test("keeps the latest result with a visible warning when history fails", async () => {
  const latest = record("run-1", "inquiry-a", "SUCCESS");
  const state = await loadExtractionState({
    latestExtraction: async () => latest,
    extractionHistory: async () => { throw new Error("history unavailable"); },
  }, "inquiry-a");
  assert.equal(state.latest, latest);
  assert.deepEqual(state.history, [latest]);
  assert.match(state.error, /历史读取失败/);
});

test("restores from history when the latest endpoint fails and rejects when both fail", async () => {
  const latest = record("run-1", "inquiry-a", "FAILED", "TIMEOUT");
  const fail = async () => { throw new Error("network unavailable"); };
  const state = await loadExtractionState({
    latestExtraction: fail,
    extractionHistory: async () => ({items: [latest]}),
  }, "inquiry-a");
  assert.equal(state.latest, latest);
  assert.match(state.error, /已从历史记录恢复/);
  await assert.rejects(loadExtractionState({latestExtraction: fail, extractionHistory: fail}, "inquiry-a"), /network unavailable/);
});

test("preserves database microsecond ordering before using the ID tie-breaker", async () => {
  const newer = {...record("aaa", "inquiry-a", "SUCCESS"), created_at: "2026-11-18T05:00:00.123999+00:00"};
  const older = {...record("zzz", "inquiry-a", "SUCCESS"), created_at: "2026-11-18T05:00:00.123001+00:00"};
  const state = await loadExtractionState({
    latestExtraction: async () => newer,
    extractionHistory: async () => ({items: [newer, older]}),
  }, "inquiry-a");
  assert.equal(state.latest, newer);
  assert.deepEqual(state.history, [newer, older]);
});
