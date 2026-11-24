const MAX_BODY_BYTES = 64 * 1024;
const UPSTREAM_TIMEOUT_MS = 15_000;
const MAX_GET_UPDATES_TIMEOUT = 10;
const TELEGRAM_API_ORIGIN = "https://api.telegram.org";

const ALLOWED_FIELDS = {
  getMe: [],
  getUpdates: ["offset", "limit", "timeout", "allowed_updates"],
  deleteWebhook: ["drop_pending_updates"],
  setMyCommands: ["commands"],
  sendMessage: ["chat_id", "text", "parse_mode", "reply_markup"],
  editMessageText: ["chat_id", "message_id", "text", "parse_mode", "reply_markup"],
  editMessageReplyMarkup: ["chat_id", "message_id", "reply_markup"],
  deleteMessage: ["chat_id", "message_id"],
  answerCallbackQuery: ["callback_query_id", "text"],
};

class RequestError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function reject(status, message) {
  throw new RequestError(status, message);
}

function jsonResponse(status, error) {
  return Response.json({ ok: false, error }, { status });
}

async function readBody(request) {
  const contentLength = request.headers.get("content-length");
  if (contentLength !== null) {
    if (!/^\d+$/.test(contentLength)) {
      reject(400, "Invalid Content-Length");
    }
    if (Number(contentLength) > MAX_BODY_BYTES) {
      reject(413, "Request body too large");
    }
  }

  if (request.body === null) {
    return new Uint8Array();
  }

  const reader = request.body.getReader();
  const chunks = [];
  let total = 0;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      total += value.byteLength;
      if (total > MAX_BODY_BYTES) {
        void reader.cancel().catch(() => {});
        reject(413, "Request body too large");
      }
      chunks.push(value);
    }
  } catch (error) {
    if (error instanceof RequestError) {
      throw error;
    }
    reject(400, "Invalid request body");
  }

  const body = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body;
}

function parseJson(body) {
  let value;
  try {
    value = JSON.parse(new TextDecoder().decode(body));
  } catch {
    reject(400, "Malformed JSON");
  }
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    reject(400, "JSON body must be an object");
  }
  return value;
}

async function parseMultipart(body, contentType) {
  let form;
  try {
    form = await new Response(body, {
      headers: { "Content-Type": contentType },
    }).formData();
  } catch {
    reject(400, "Malformed multipart body");
  }

  const value = Object.create(null);
  for (const [name, fieldValue] of form.entries()) {
    if (typeof fieldValue !== "string") {
      reject(400, "Multipart files are not allowed");
    }
    if (Object.hasOwn(value, name)) {
      reject(400, "Repeated multipart fields are not allowed");
    }
    value[name] = fieldValue;
  }
  return value;
}

function requireFields(values, fields) {
  for (const field of fields) {
    if (!Object.hasOwn(values, field)) {
      reject(400, `Missing required field: ${field}`);
    }
  }
}

function integerValue(values, field, multipart, { min, max } = {}) {
  if (!Object.hasOwn(values, field)) {
    return;
  }
  const raw = values[field];
  if (multipart && !/^-?\d+$/.test(raw)) {
    reject(400, `Invalid integer field: ${field}`);
  }
  const value = multipart ? Number(raw) : raw;
  if (!Number.isSafeInteger(value)) {
    reject(400, `Invalid integer field: ${field}`);
  }
  if ((min !== undefined && value < min) || (max !== undefined && value > max)) {
    reject(400, `Integer field out of range: ${field}`);
  }
}

function stringValue(values, field, multipart, { maxLength, allowEmpty = false } = {}) {
  if (!Object.hasOwn(values, field)) {
    return;
  }
  const value = values[field];
  if (typeof value !== "string" || (!allowEmpty && value.length === 0)) {
    reject(400, `Invalid string field: ${field}`);
  }
  if (maxLength !== undefined && Array.from(value).length > maxLength) {
    reject(400, `String field too long: ${field}`);
  }
}

function chatIdValue(values, multipart) {
  if (!Object.hasOwn(values, "chat_id")) {
    return;
  }
  const value = values.chat_id;
  if (multipart || typeof value === "string") {
    stringValue(values, "chat_id", multipart);
  } else if (!Number.isSafeInteger(value)) {
    reject(400, "Invalid chat_id");
  }
}

function booleanValue(values, field, multipart) {
  if (!Object.hasOwn(values, field)) {
    return;
  }
  const value = values[field];
  if (multipart ? value !== "true" && value !== "false" : typeof value !== "boolean") {
    reject(400, `Invalid boolean field: ${field}`);
  }
}

function structuredValue(values, field, multipart, expectedType) {
  if (!Object.hasOwn(values, field)) {
    return;
  }
  let value = values[field];
  if (multipart) {
    try {
      value = JSON.parse(value);
    } catch {
      reject(400, `Invalid JSON field: ${field}`);
    }
  }
  if (value === null || typeof value !== "object") {
    reject(400, `Invalid object field: ${field}`);
  }
  if (expectedType === "array" && !Array.isArray(value)) {
    reject(400, `Invalid array field: ${field}`);
  }
  if (expectedType === "object" && Array.isArray(value)) {
    reject(400, `Invalid object field: ${field}`);
  }
  return value;
}

function validate(method, values, multipart) {
  const allowed = ALLOWED_FIELDS[method];
  for (const field of Object.keys(values)) {
    if (!allowed.includes(field)) {
      reject(400, `Unknown field: ${field}`);
    }
  }

  switch (method) {
    case "getMe":
      break;
    case "getUpdates": {
      integerValue(values, "offset", multipart);
      integerValue(values, "limit", multipart, { min: 1, max: 100 });
      integerValue(values, "timeout", multipart, { min: 0, max: MAX_GET_UPDATES_TIMEOUT });
      const updates = structuredValue(values, "allowed_updates", multipart, "array");
      if (updates && updates.some((item) => item !== "message" && item !== "callback_query")) {
        reject(400, "Unsupported allowed_updates value");
      }
      break;
    }
    case "deleteWebhook":
      booleanValue(values, "drop_pending_updates", multipart);
      break;
    case "setMyCommands":
      requireFields(values, ["commands"]);
      structuredValue(values, "commands", multipart, "array");
      break;
    case "sendMessage":
      requireFields(values, ["chat_id", "text"]);
      chatIdValue(values, multipart);
      stringValue(values, "text", multipart, { maxLength: 4096 });
      stringValue(values, "parse_mode", multipart);
      structuredValue(values, "reply_markup", multipart, "object");
      break;
    case "editMessageText":
      requireFields(values, ["chat_id", "message_id", "text"]);
      chatIdValue(values, multipart);
      integerValue(values, "message_id", multipart, { min: 1 });
      stringValue(values, "text", multipart, { maxLength: 4096 });
      stringValue(values, "parse_mode", multipart);
      structuredValue(values, "reply_markup", multipart, "object");
      break;
    case "editMessageReplyMarkup":
      requireFields(values, ["chat_id", "message_id"]);
      chatIdValue(values, multipart);
      integerValue(values, "message_id", multipart, { min: 1 });
      structuredValue(values, "reply_markup", multipart, "object");
      break;
    case "deleteMessage":
      requireFields(values, ["chat_id", "message_id"]);
      chatIdValue(values, multipart);
      integerValue(values, "message_id", multipart, { min: 1 });
      break;
    case "answerCallbackQuery":
      requireFields(values, ["callback_query_id"]);
      stringValue(values, "callback_query_id", multipart);
      stringValue(values, "text", multipart, { maxLength: 200, allowEmpty: true });
      break;
  }
}

async function parseRequest(request) {
  const contentType = request.headers.get("content-type") || "";
  const mediaType = contentType.split(";", 1)[0].trim().toLowerCase();
  if (mediaType !== "application/json" && mediaType !== "multipart/form-data") {
    reject(415, "Unsupported Content-Type");
  }

  const body = await readBody(request);
  const multipart = mediaType === "multipart/form-data";
  const values = multipart
    ? await parseMultipart(body, contentType)
    : parseJson(body);
  return { body, contentType, multipart, values };
}

export default {
  async fetch(request, env) {
    try {
      const url = new URL(request.url);
      const method = url.pathname.slice(1);
      if (
        request.method !== "POST" ||
        url.search !== "" ||
        !url.pathname.startsWith("/") ||
        !Object.hasOwn(ALLOWED_FIELDS, method)
      ) {
        return request.method === "POST"
          ? jsonResponse(404, "Not found")
          : new Response(jsonResponse(405, "Method not allowed").body, {
              status: 405,
              headers: { "Content-Type": "application/json", Allow: "POST" },
            });
      }

      if (
        typeof env.RELAY_KEY !== "string" ||
        env.RELAY_KEY.length === 0 ||
        request.headers.get("x-relay-key") !== env.RELAY_KEY
      ) {
        return jsonResponse(403, "Forbidden");
      }
      if (typeof env.BOT_TOKEN !== "string" || env.BOT_TOKEN.length === 0) {
        return jsonResponse(500, "Relay is not configured");
      }

      const { body, contentType, multipart, values } = await parseRequest(request);
      validate(method, values, multipart);

      const emptyMultipart = multipart && Object.keys(values).length === 0;
      const upstreamRequestBody = emptyMultipart ? new TextEncoder().encode("{}") : body;
      const upstreamRequestContentType = emptyMultipart ? "application/json" : contentType;

      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), UPSTREAM_TIMEOUT_MS);
      try {
        const upstream = await fetch(
          `${TELEGRAM_API_ORIGIN}/bot${env.BOT_TOKEN}/${method}`,
          {
            method: "POST",
            headers: { "Content-Type": upstreamRequestContentType },
            body: upstreamRequestBody,
            redirect: "manual",
            signal: controller.signal,
          },
        );
        if (upstream.status >= 300 && upstream.status <= 399) {
          return jsonResponse(502, "Bad gateway");
        }
        const upstreamBody = await upstream.arrayBuffer();
        const headers = new Headers();
        const upstreamContentType = upstream.headers.get("content-type");
        if (upstreamContentType !== null) {
          headers.set("Content-Type", upstreamContentType);
        }
        return new Response(upstreamBody, { status: upstream.status, headers });
      } catch (error) {
        if (controller.signal.aborted || error?.name === "TimeoutError") {
          return jsonResponse(504, "Upstream timeout");
        }
        return jsonResponse(502, "Bad gateway");
      } finally {
        clearTimeout(timeout);
      }
    } catch (error) {
      if (error instanceof RequestError) {
        return jsonResponse(error.status, error.message);
      }
      return jsonResponse(400, "Invalid request");
    }
  },
};
