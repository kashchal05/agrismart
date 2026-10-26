// Thin API client for the Agrismart backend. Token is kept in localStorage.
const TOKEN_KEY = "agrismart_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable (private mode) — session-only */
  }
}

export interface Field {
  id: string;
  name: string;
  geometry: GeoJSON.Polygon;
  area_ha: number;
  centroid_lat: number;
  centroid_lon: number;
  county: string | null;
  county_fips: string | null;
  state: string | null;
  created_at: string;
}

export interface Observation {
  scene_date: string;
  ndvi_mean: number;
  ndvi_p10: number;
  ndvi_p90: number;
  evi_mean: number | null;
  ndwi_mean: number | null;
  clear_fraction: number;
  cloud_pct: number | null;
}

export interface CropReason {
  factor: string;
  direction: "favors" | "limits";
  weight: number;
}

export interface CropRec {
  crop: string;
  suitability: number;
  why: CropReason[];
}

export interface Recommendation {
  field_id: string;
  field_name: string;
  recommendations: CropRec[];
  trained: string | null;
}

// FastAPI returns `detail` as a string (HTTPException) or a list of error objects
// (422 validation). Turn either into a readable message.
function parseError(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => (e && typeof e === "object" && "msg" in e ? String((e as { msg: unknown }).msg) : String(e)))
      .join("; ");
  }
  return null;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const resp = await fetch(`/api${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(parseError(body) || `Request failed (${resp.status})`);
  }
  return resp.status === 204 ? (undefined as T) : ((await resp.json()) as T);
}

export const api = {
  register: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<{ email: string }>("/auth/me"),
  listFields: () => request<Field[]>("/fields"),
  createField: (name: string, geometry: GeoJSON.Polygon) =>
    request<Field>("/fields", { method: "POST", body: JSON.stringify({ name, geometry }) }),
  deleteField: (id: string) => request<void>(`/fields/${id}`, { method: "DELETE" }),
  recommend: (id: string) => request<Recommendation>(`/fields/${id}/recommend`),
  observations: (id: string) => request<Observation[]>(`/fields/${id}/observations`),
  ingest: (id: string) =>
    request<{ status: string }>(`/fields/${id}/ingest`, { method: "POST" }),
};
