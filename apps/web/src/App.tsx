import { useCallback, useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import type { CropRec, Field } from "./api";
import { api, getToken, setToken } from "./api";
import { Auth } from "./Auth";

const TEXAS_CENTER: [number, number] = [-99.5, 31.3];

function fieldsToGeoJSON(fields: Field[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: fields.map((f) => ({
      type: "Feature",
      id: f.id,
      properties: { name: f.name },
      geometry: f.geometry,
    })),
  };
}

function renderRecs(state: "loading" | { error: string } | CropRec[] | undefined) {
  if (!state || state === "loading") return null;
  if ("error" in state) return <div className="rec-error">{state.error}</div>;
  return (
    <div className="recs">
      {state.map((r, i) => {
        const pct = Math.round(r.suitability * 100);
        const top = r.why[0];
        return (
          <div key={r.crop} className="rec-row">
            <div className="rec-head">
              <span className="rec-rank">{i + 1}</span>
              <span className="rec-crop">{r.crop}</span>
              <span className="rec-pct">{pct}%</span>
            </div>
            <div className="rec-bar"><div className="rec-fill" style={{ width: `${pct}%` }} /></div>
            {top && (
              <div className="rec-why">
                {top.direction === "favors" ? "✓" : "⚠"} {top.factor} {top.direction} this crop
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function App() {
  const [authed, setAuthed] = useState(!!getToken());
  if (!authed) return <Auth onAuthed={() => setAuthed(true)} />;
  return <Dashboard onLogout={() => { setToken(null); setAuthed(false); }} />;
}

function Dashboard({ onLogout }: { onLogout: () => void }) {
  const mapRef = useRef<maplibregl.Map | null>(null);
  const mapContainer = useRef<HTMLDivElement | null>(null);
  const [fields, setFields] = useState<Field[]>([]);
  const [email, setEmail] = useState<string>("");
  const [drawing, setDrawing] = useState(false);
  const [vertexCount, setVertexCount] = useState(0);
  // field_id -> "loading" | error string | crop recommendations
  const [recs, setRecs] = useState<Record<string, "loading" | { error: string } | CropRec[]>>({});

  // Drawing state lives in refs so the map click handler never sees stale values.
  const drawingRef = useRef(false);
  const vertsRef = useRef<[number, number][]>([]);

  const refreshFields = useCallback(async () => {
    const list = await api.listFields();
    setFields(list);
    const src = mapRef.current?.getSource("fields") as maplibregl.GeoJSONSource | undefined;
    src?.setData(fieldsToGeoJSON(list));
  }, []);

  const renderDraw = useCallback(() => {
    const verts = vertsRef.current;
    const features: GeoJSON.Feature[] = verts.map((c) => ({
      type: "Feature", properties: {}, geometry: { type: "Point", coordinates: c },
    }));
    if (verts.length >= 2) {
      features.push({
        type: "Feature", properties: {},
        geometry: { type: "LineString", coordinates: [...verts, verts[0]] },
      });
    }
    const src = mapRef.current?.getSource("draw") as maplibregl.GeoJSONSource | undefined;
    src?.setData({ type: "FeatureCollection", features });
    setVertexCount(verts.length);
  }, []);

  // Init map once.
  useEffect(() => {
    if (mapRef.current || !mapContainer.current) return;
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: "https://demotiles.maplibre.org/style.json",
      center: TEXAS_CENTER,
      zoom: 5,
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl(), "bottom-right");

    map.on("load", () => {
      map.addSource("fields", { type: "geojson", data: fieldsToGeoJSON([]) });
      map.addLayer({
        id: "fields-fill", type: "fill", source: "fields",
        paint: { "fill-color": "#2e7d32", "fill-opacity": 0.3 },
      });
      map.addLayer({
        id: "fields-outline", type: "line", source: "fields",
        paint: { "line-color": "#1b5e20", "line-width": 2 },
      });
      map.addSource("draw", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "draw-line", type: "line", source: "draw",
        paint: { "line-color": "#ff6f00", "line-width": 2, "line-dasharray": [2, 1] },
      });
      map.addLayer({
        id: "draw-pts", type: "circle", source: "draw",
        paint: { "circle-radius": 5, "circle-color": "#ff6f00", "circle-stroke-color": "#fff",
          "circle-stroke-width": 2 },
      });
      refreshFields().catch(() => undefined);
    });

    map.on("click", (e) => {
      if (!drawingRef.current) return;
      vertsRef.current = [...vertsRef.current, [e.lngLat.lng, e.lngLat.lat]];
      renderDraw();
    });

    api.me().then((u) => setEmail(u.email)).catch(() => undefined);
    return () => { map.remove(); mapRef.current = null; };
  }, [refreshFields, renderDraw]);

  function startDraw() {
    vertsRef.current = [];
    drawingRef.current = true;
    setDrawing(true);
    renderDraw();
  }

  function cancelDraw() {
    vertsRef.current = [];
    drawingRef.current = false;
    setDrawing(false);
    renderDraw();
  }

  async function finishDraw() {
    const verts = vertsRef.current;
    if (verts.length < 3) return;
    const name = window.prompt("Name this field:", `Field ${fields.length + 1}`);
    if (!name) return;
    const ring = [...verts, verts[0]];
    try {
      await api.createField(name, { type: "Polygon", coordinates: [ring] });
      cancelDraw();
      await refreshFields();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to save field");
    }
  }

  function flyTo(f: Field) {
    mapRef.current?.flyTo({ center: [f.centroid_lon, f.centroid_lat], zoom: 13 });
  }

  async function remove(f: Field, e: React.MouseEvent) {
    e.stopPropagation();
    if (!window.confirm(`Delete "${f.name}"?`)) return;
    await api.deleteField(f.id);
    await refreshFields();
  }

  async function getRecs(f: Field, e: React.MouseEvent) {
    e.stopPropagation();
    setRecs((r) => ({ ...r, [f.id]: "loading" }));
    try {
      const res = await api.recommend(f.id);
      setRecs((r) => ({ ...r, [f.id]: res.recommendations }));
    } catch (err) {
      setRecs((r) => ({ ...r, [f.id]: { error: err instanceof Error ? err.message : "failed" } }));
    }
  }

  return (
    <div className="app">
      <div className="topbar">
        <h1>🌾 Agrismart 2.0</h1>
        <div>
          <span className="user">{email}</span>
          <button className="secondary" onClick={onLogout}>Log out</button>
        </div>
      </div>
      <div className="layout">
        <aside className="sidebar">
          <div className="sidebar-head">
            <h2>Your fields ({fields.length})</h2>
            <p>Draw a field on the map to monitor its crop health.</p>
          </div>
          {fields.length === 0 ? (
            <div className="empty">No fields yet.<br />Click “Draw field” and trace a boundary.</div>
          ) : (
            <ul className="field-list">
              {fields.map((f) => (
                <li key={f.id} className="field-item" onClick={() => flyTo(f)}>
                  <a className="del" onClick={(e) => remove(f, e)}>delete</a>
                  <h3>{f.name}</h3>
                  <div className="meta">
                    {f.area_ha.toFixed(1)} ha
                    {f.county ? ` · ${f.county} County, ${f.state}` : ""}<br />
                    {f.centroid_lat.toFixed(4)}, {f.centroid_lon.toFixed(4)}
                  </div>
                  <button className="rec-btn" onClick={(e) => getRecs(f, e)}
                    disabled={recs[f.id] === "loading"}>
                    {recs[f.id] === "loading" ? "Analyzing soil & climate…" : "🌱 Recommend crops"}
                  </button>
                  {renderRecs(recs[f.id])}
                </li>
              ))}
            </ul>
          )}
        </aside>
        <div className="map-wrap">
          <div id="map" ref={mapContainer} />
          <div className="draw-bar">
            {!drawing ? (
              <button onClick={startDraw}>✏️ Draw field</button>
            ) : (
              <>
                <span>{vertexCount} point{vertexCount === 1 ? "" : "s"} — click to add</span>
                <button onClick={finishDraw} disabled={vertexCount < 3}>Finish</button>
                <button className="secondary" onClick={cancelDraw}>Cancel</button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
