export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export async function api<T>(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API}${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
      signal: signal ?? AbortSignal.timeout(22000),
    });
  } catch (cause) {
    const timedOut =
      cause instanceof DOMException &&
      (cause.name === "TimeoutError" || cause.name === "AbortError");
    throw new Error(
      timedOut
        ? "El backend tardó demasiado en responder. Reintenta el análisis."
        : "No se pudo conectar con el backend. Verifica que Podman y FastAPI estén activos.",
      { cause },
    );
  }
  const data: unknown = await response.json();
  if (!response.ok) {
    const message =
      typeof data === "object" &&
      data !== null &&
      "error" in data &&
      typeof data.error === "object" &&
      data.error !== null &&
      "message" in data.error
        ? String(data.error.message)
        : `Error HTTP ${response.status}`;
    throw new Error(message);
  }
  return data as T;
}
