// Calls to the local ffai service (python -m ffai serve). It only listens on
// 127.0.0.1. The ESPN data and the AI key go there and nowhere else.

export class ServiceDownError extends Error {
  constructor(base) {
    super(`The ffai service is not running at ${base}. Start it with:  python -m ffai serve`);
  }
}
// The service answered with an error. `kind` is "parse" for an ESPN format problem.
export class ServiceError extends Error {
  constructor(status, message, kind) {
    super(message);
    this.status = status;
    this.kind = kind;
  }
}

async function request(base, method, path, body, fetchFn = fetch) {
  let response;
  try {
    response = await fetchFn(`${base}${path}`, {
      method,
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ServiceDownError(base);
  }
  let data = null;
  try {
    data = await response.json();
  } catch {
    // keep data = null; handled below
  }
  if (!response.ok) {
    throw new ServiceError(response.status, (data && data.error) || `Service answered HTTP ${response.status}`, data && data.kind);
  }
  return data;
}

export const health = (base, fetchFn) => request(base, "GET", "/health", undefined, fetchFn);
export const analyze = (base, payload, fetchFn) => request(base, "POST", "/analyze", payload, fetchFn);
export const explain = (base, result, ai, fetchFn) => request(base, "POST", "/explain", { result, ai }, fetchFn);
