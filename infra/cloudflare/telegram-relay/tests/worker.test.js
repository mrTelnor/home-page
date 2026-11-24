import assert from "node:assert/strict";
import { test } from "node:test";
import worker from "../worker.js";

const ENV = { BOT_TOKEN: "test-bot-token", RELAY_KEY: "test-relay-key" };
const RELAY_URL = "https://relay.example";

function request(method, payload = {}, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    "X-Relay-Key": ENV.RELAY_KEY,
    ...options.headers,
  };
  const httpMethod = options.httpMethod || "POST";
  return new Request(`${RELAY_URL}/${method}`, {
    method: httpMethod,
    headers,
    body: httpMethod === "GET" || httpMethod === "HEAD"
      ? undefined
      : options.rawBody ?? JSON.stringify(payload),
  });
}

function mockTelegram(t, implementation) {
  const calls = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    calls.push({ url, options });
    if (implementation) {
      return implementation(url, options);
    }
    return Response.json({ ok: true, result: true });
  });
  return calls;
}

const methods = [
  ["getMe", {}],
  [
    "getUpdates",
    { offset: -1, limit: 100, timeout: 10, allowed_updates: ["message", "callback_query"] },
  ],
  ["deleteWebhook", { drop_pending_updates: true }],
  ["setMyCommands", { commands: [{ command: "start", description: "Start" }] }],
  [
    "sendMessage",
    { chat_id: 123, text: "hello", parse_mode: "HTML", reply_markup: { inline_keyboard: [] } },
  ],
  [
    "editMessageText",
    { chat_id: "@channel", message_id: 10, text: "edited", reply_markup: { inline_keyboard: [] } },
  ],
  ["editMessageReplyMarkup", { chat_id: 123, message_id: 10, reply_markup: { inline_keyboard: [] } }],
  ["deleteMessage", { chat_id: 123, message_id: 10 }],
  ["answerCallbackQuery", { callback_query_id: "callback-id", text: "Done" }],
];

for (const [method, payload] of methods) {
  test(`${method} reaches Telegram with its token and allowed payload`, async (t) => {
    const calls = mockTelegram(t);
    const response = await worker.fetch(request(method, payload), ENV);

    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { ok: true, result: true });
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, `https://api.telegram.org/bot${ENV.BOT_TOKEN}/${method}`);
    assert.equal(calls[0].options.method, "POST");
    assert.equal(calls[0].options.headers["Content-Type"], "application/json");
    assert.deepEqual(JSON.parse(new TextDecoder().decode(calls[0].options.body)), payload);
  });
}

test("GET, unknown methods and paths, and a wrong relay key are rejected without fetch", async (t) => {
  const calls = mockTelegram(t);
  const cases = [
    [request("getMe", {}, { httpMethod: "GET" }), 405],
    [request("unknown"), 404],
    [new Request(`${RELAY_URL}/sendMessage/extra`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Relay-Key": ENV.RELAY_KEY },
      body: "{}",
    }), 404],
    [request("getMe", {}, { headers: { "X-Relay-Key": "wrong" } }), 403],
  ];

  for (const [incoming, status] of cases) {
    const response = await worker.fetch(incoming, ENV);
    assert.equal(response.status, status);
  }
  assert.equal(calls.length, 0);
});

test("multipart fields are validated and relayed as multipart", async (t) => {
  const calls = mockTelegram(t);
  const form = new FormData();
  form.append("chat_id", "123");
  form.append("text", "multipart text");
  form.append("reply_markup", JSON.stringify({ inline_keyboard: [] }));
  const incoming = new Request(`${RELAY_URL}/sendMessage`, {
    method: "POST",
    headers: { "X-Relay-Key": ENV.RELAY_KEY },
    body: form,
  });

  const response = await worker.fetch(incoming, ENV);
  assert.equal(response.status, 200);
  assert.equal(calls.length, 1);
  assert.match(calls[0].options.headers["Content-Type"], /^multipart\/form-data; boundary=/);
  const forwarded = await new Response(calls[0].options.body, {
    headers: { "Content-Type": calls[0].options.headers["Content-Type"] },
  }).formData();
  assert.equal(forwarded.get("chat_id"), "123");
  assert.equal(forwarded.get("text"), "multipart text");
  assert.equal(forwarded.get("reply_markup"), JSON.stringify({ inline_keyboard: [] }));
});

test("multipart getUpdates accepts serialized allowed_updates", async (t) => {
  const calls = mockTelegram(t);
  const form = new FormData();
  form.append("limit", "100");
  form.append("timeout", "10");
  form.append("allowed_updates", JSON.stringify(["message", "callback_query"]));
  const response = await worker.fetch(new Request(`${RELAY_URL}/getUpdates`, {
    method: "POST",
    headers: { "X-Relay-Key": ENV.RELAY_KEY },
    body: form,
  }), ENV);

  assert.equal(response.status, 200);
  assert.equal(calls.length, 1);
});

test("multipart files, repeated fields and unknown fields are rejected", async (t) => {
  const calls = mockTelegram(t);
  const withFile = new FormData();
  withFile.append("chat_id", "123");
  withFile.append("text", new File(["secret"], "message.txt"));
  const repeated = new FormData();
  repeated.append("callback_query_id", "one");
  repeated.append("callback_query_id", "two");

  const fileResponse = await worker.fetch(new Request(`${RELAY_URL}/sendMessage`, {
    method: "POST", headers: { "X-Relay-Key": ENV.RELAY_KEY }, body: withFile,
  }), ENV);
  const repeatedResponse = await worker.fetch(new Request(`${RELAY_URL}/answerCallbackQuery`, {
    method: "POST", headers: { "X-Relay-Key": ENV.RELAY_KEY }, body: repeated,
  }), ENV);
  const extraResponse = await worker.fetch(request("deleteMessage", {
    chat_id: 123, message_id: 10, extra: "not allowed",
  }), ENV);

  assert.equal(fileResponse.status, 400);
  assert.equal(repeatedResponse.status, 400);
  assert.equal(extraResponse.status, 400);
  assert.equal(calls.length, 0);
});

test("malformed JSON, non-object JSON and unsupported content types are rejected", async (t) => {
  const calls = mockTelegram(t);
  const responses = [
    await worker.fetch(request("getMe", {}, { rawBody: "{" }), ENV),
    await worker.fetch(request("getMe", {}, { rawBody: "[]" }), ENV),
    await worker.fetch(request("getMe", {}, {
      rawBody: "{}", headers: { "Content-Type": "text/plain" },
    }), ENV),
  ];

  assert.deepEqual(responses.map((response) => response.status), [400, 400, 415]);
  assert.equal(calls.length, 0);
});

test("body is limited by Content-Length and by actual streamed bytes", async (t) => {
  const calls = mockTelegram(t);
  const declared = await worker.fetch(request("getMe", {}, {
    rawBody: "{}", headers: { "Content-Length": String(64 * 1024 + 1) },
  }), ENV);
  const actual = await worker.fetch(request("sendMessage", {}, {
    rawBody: JSON.stringify({ chat_id: 1, text: "x".repeat(64 * 1024) }),
  }), ENV);

  assert.equal(declared.status, 413);
  assert.equal(actual.status, 413);
  assert.equal(calls.length, 0);
});

test("getUpdates ranges, text lengths and allowed_updates are validated", async (t) => {
  const calls = mockTelegram(t);
  const invalidPayloads = [
    ["getUpdates", { limit: 0 }],
    ["getUpdates", { limit: 101 }],
    ["getUpdates", { timeout: 11 }],
    ["getUpdates", { allowed_updates: ["edited_message"] }],
    ["sendMessage", { chat_id: 1, text: "x".repeat(4097) }],
    ["answerCallbackQuery", { callback_query_id: "id", text: "x".repeat(201) }],
  ];

  for (const [method, payload] of invalidPayloads) {
    const response = await worker.fetch(request(method, payload), ENV);
    assert.equal(response.status, 400);
  }
  assert.equal(calls.length, 0);
});

test("Telegram 200, 400, 403 and 429 responses retain status and JSON", async (t) => {
  const payloads = [
    [200, { ok: true, result: { id: 1 } }],
    [400, { ok: false, error_code: 400, description: "Bad Request" }],
    [403, { ok: false, error_code: 403, description: "Forbidden" }],
    [429, { ok: false, error_code: 429, description: "Too Many Requests", parameters: { retry_after: 3 } }],
  ];

  for (const [status, payload] of payloads) {
    t.mock.method(globalThis, "fetch", async () => Response.json(payload, { status }));
    const response = await worker.fetch(request("getMe"), ENV);
    assert.equal(response.status, status);
    assert.deepEqual(await response.json(), payload);
    t.mock.restoreAll();
  }
});

test("network errors and timeouts return generic 502 and 504 responses", async (t) => {
  t.mock.method(globalThis, "fetch", async () => {
    throw new Error(`fetch failed for ${ENV.BOT_TOKEN}`);
  });
  const failed = await worker.fetch(request("getMe"), ENV);
  const failedBody = await failed.text();
  assert.equal(failed.status, 502);
  assert.equal(failedBody.includes(ENV.BOT_TOKEN), false);
  assert.equal(failedBody.includes(ENV.RELAY_KEY), false);
  t.mock.restoreAll();

  t.mock.method(globalThis, "fetch", async () => {
    throw new DOMException("Timed out", "TimeoutError");
  });
  const timedOut = await worker.fetch(request("getMe"), ENV);
  assert.equal(timedOut.status, 504);
  assert.equal((await timedOut.text()).includes(ENV.BOT_TOKEN), false);
});

test("relay does not write secrets, payloads, headers or upstream URLs to console", async (t) => {
  const calls = [];
  for (const method of ["log", "info", "warn", "error", "debug"]) {
    t.mock.method(console, method, (...args) => calls.push(args));
  }
  mockTelegram(t);
  const response = await worker.fetch(request("sendMessage", {
    chat_id: 123, text: "private payload",
  }), ENV);

  assert.equal(response.status, 200);
  assert.deepEqual(calls, []);
  const responseText = await response.text();
  assert.equal(responseText.includes(ENV.BOT_TOKEN), false);
  assert.equal(responseText.includes(ENV.RELAY_KEY), false);
  assert.equal(responseText.includes("private payload"), false);
});

test("a body of exactly 64 KiB is accepted by both byte limits", async (t) => {
  const calls = mockTelegram(t);
  const rawBody = "{}" + " ".repeat(64 * 1024 - 2);
  const incoming = request("getMe", {}, {
    rawBody,
    headers: { "Content-Length": String(rawBody.length) },
  });

  const response = await worker.fetch(incoming, ENV);

  assert.equal(new TextEncoder().encode(rawBody).byteLength, 64 * 1024);
  assert.equal(response.status, 200);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].options.body.byteLength, 64 * 1024);
});

test("an understated Content-Length does not bypass the actual byte limit", async (t) => {
  const calls = mockTelegram(t);
  const rawBody = JSON.stringify({ chat_id: 1, text: "x".repeat(64 * 1024) });
  const incoming = request("sendMessage", {}, {
    rawBody,
    headers: { "Content-Length": "2" },
  });

  const response = await worker.fetch(incoming, ENV);

  assert.equal(response.status, 413);
  assert.equal(calls.length, 0);
});

test("a chunked body without Content-Length cannot bypass the actual byte limit", async (t) => {
  const calls = mockTelegram(t);
  const chunk = new Uint8Array(32 * 1024).fill(32);
  const body = new ReadableStream({
    start(controller) {
      controller.enqueue(chunk);
      controller.enqueue(chunk);
      controller.enqueue(chunk);
      controller.close();
    },
  });
  const incoming = new Request(`${RELAY_URL}/getMe`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Relay-Key": ENV.RELAY_KEY,
    },
    body,
    duplex: "half",
  });

  const response = await worker.fetch(incoming, ENV);

  assert.equal(response.status, 413);
  assert.equal(calls.length, 0);
});

test("an aiogram-style multipart body retains its boundary and string fields", async (t) => {
  const calls = mockTelegram(t);
  const boundary = "----aiogram-test-boundary";
  const contentType = `multipart/form-data; boundary=${boundary}`;
  const rawBody = [
    `--${boundary}\r\n`,
    'Content-Disposition: form-data; name="chat_id"\r\n\r\n',
    "123\r\n",
    `--${boundary}\r\n`,
    'Content-Disposition: form-data; name="text"\r\n\r\n',
    "hello from aiogram\r\n",
    `--${boundary}\r\n`,
    'Content-Disposition: form-data; name="reply_markup"\r\n\r\n',
    '{"inline_keyboard":[]}\r\n',
    `--${boundary}--\r\n`,
  ].join("");
  const incoming = new Request(`${RELAY_URL}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": contentType, "X-Relay-Key": ENV.RELAY_KEY },
    body: rawBody,
  });

  const response = await worker.fetch(incoming, ENV);

  assert.equal(response.status, 200);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].options.headers["Content-Type"], contentType);
  assert.equal(new TextDecoder().decode(calls[0].options.body), rawBody);
});

test("multipart without a boundary is rejected before upstream", async (t) => {
  const calls = mockTelegram(t);
  const incoming = request("getMe", {}, {
    rawBody: "",
    headers: { "Content-Type": "multipart/form-data" },
  });

  const response = await worker.fetch(incoming, ENV);

  assert.equal(response.status, 400);
  assert.equal(calls.length, 0);
});

test("multipart unknown fields, including __proto__, are rejected", async (t) => {
  const calls = mockTelegram(t);

  for (const fieldName of ["extra", "__proto__"]) {
    const form = new FormData();
    form.append(fieldName, "not allowed");
    const response = await worker.fetch(new Request(`${RELAY_URL}/getMe`, {
      method: "POST",
      headers: { "X-Relay-Key": ENV.RELAY_KEY },
      body: form,
    }), ENV);

    assert.equal(response.status, 400, `field ${fieldName} must be rejected`);
  }
  assert.equal(calls.length, 0);
});

test("the upstream abort signal fires after exactly 15 seconds with a generic 504", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  let upstreamSignal;
  t.mock.method(globalThis, "fetch", async (url, options) => {
    upstreamSignal = options.signal;
    return new Promise((resolve, reject) => {
      options.signal.addEventListener("abort", () => reject(options.signal.reason), { once: true });
    });
  });

  const pending = worker.fetch(request("getMe"), ENV);
  await new Promise((resolve) => setImmediate(resolve));
  assert.ok(upstreamSignal, "upstream request must start");
  t.mock.timers.tick(14_999);
  assert.equal(upstreamSignal.aborted, false);
  t.mock.timers.tick(1);
  assert.equal(upstreamSignal.aborted, true);

  const response = await pending;
  assert.equal(response.status, 504);
  assert.deepEqual(await response.json(), { ok: false, error: "Upstream timeout" });
});


test("upstream redirects are rejected without calling another origin", async (t) => {
  const externalUrl = `https://attacker.example/${ENV.BOT_TOKEN}`;
  const calls = mockTelegram(t, async (url, options) => {
    assert.equal(options.redirect, "manual");
    return new Response("redirect", {
      status: 302,
      headers: { "Content-Type": "text/plain", Location: externalUrl },
    });
  });

  const response = await worker.fetch(request("getMe"), ENV);
  const responseBody = await response.text();

  assert.equal(response.status, 502);
  assert.deepEqual(JSON.parse(responseBody), { ok: false, error: "Bad gateway" });
  assert.equal(response.headers.get("Location"), null);
  assert.equal(responseBody.includes(externalUrl), false);
  assert.equal(responseBody.includes(ENV.BOT_TOKEN), false);
  assert.equal(responseBody.includes(ENV.RELAY_KEY), false);
  assert.equal(calls.length, 1);
  assert.equal(new URL(calls[0].url).origin, "https://api.telegram.org");
});

test("an upstream body read failure returns a generic 502", async (t) => {
  t.mock.method(globalThis, "fetch", async () => {
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('{"ok":true'));
        controller.error(new Error(`Body failed for ${ENV.BOT_TOKEN}`));
      },
    });
    return new Response(body, {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });

  const response = await worker.fetch(request("getMe"), ENV);
  const responseBody = await response.text();

  assert.equal(response.status, 502);
  assert.deepEqual(JSON.parse(responseBody), { ok: false, error: "Bad gateway" });
  assert.equal(responseBody.includes(ENV.BOT_TOKEN), false);
  assert.equal(responseBody.includes("Body failed"), false);
});

test("an endless upstream body after headers times out at 15 seconds with 504", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  let upstreamSignal;
  t.mock.method(globalThis, "fetch", async (url, options) => {
    upstreamSignal = options.signal;
    const body = new ReadableStream({
      start(bodyController) {
        bodyController.enqueue(new TextEncoder().encode("{"));
        options.signal.addEventListener("abort", () => {
          bodyController.error(options.signal.reason);
        }, { once: true });
      },
    });
    return new Response(body, {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });

  const pending = worker.fetch(request("getMe"), ENV);
  await new Promise((resolve) => setImmediate(resolve));
  assert.ok(upstreamSignal, "upstream response headers must arrive");
  t.mock.timers.tick(14_999);
  assert.equal(upstreamSignal.aborted, false);
  t.mock.timers.tick(1);
  assert.equal(upstreamSignal.aborted, true);

  const response = await pending;
  assert.equal(response.status, 504);
  assert.deepEqual(await response.json(), { ok: false, error: "Upstream timeout" });
});


test("an empty multipart getMe is sent upstream as an empty JSON object", async (t) => {
  const boundary = "----empty-aiogram-multipart";
  const rawBody = `--${boundary}--\r\n`;
  const telegramResponse = { ok: true, result: { id: 1, is_bot: true, username: "test_bot" } };
  const calls = mockTelegram(t, async () => Response.json(telegramResponse));

  const response = await worker.fetch(request("getMe", {}, {
    rawBody,
    headers: { "Content-Type": `multipart/form-data; boundary=${boundary}` },
  }), ENV);

  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), telegramResponse);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].options.headers["Content-Type"], "application/json");
  assert.equal(new TextDecoder().decode(calls[0].options.body), "{}");
});

test("an empty multipart body is still rejected when required fields are missing", async (t) => {
  const boundary = "----empty-required-fields";
  const calls = mockTelegram(t);
  const response = await worker.fetch(request("sendMessage", {}, {
    rawBody: `--${boundary}--\r\n`,
    headers: { "Content-Type": `multipart/form-data; boundary=${boundary}` },
  }), ENV);

  assert.equal(response.status, 400);
  assert.equal(calls.length, 0);
});
