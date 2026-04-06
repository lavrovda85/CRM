"use client";

import { useEffect, useMemo, useRef } from "react";

declare global {
  interface Window {
    ymaps?: any;
  }
}

interface Props {
  address: string;
  latitude: string;
  longitude: string;
  onAddressChange: (v: string) => void;
  onLatitudeChange: (v: string) => void;
  onLongitudeChange: (v: string) => void;
}

const SCRIPT_ID = "yandex-maps-script";

export function YandexTaskLocationPicker(props: Props) {
  const mapRef = useRef<HTMLDivElement | null>(null);
  const initialized = useRef(false);
  const mapObj = useRef<any>(null);
  const markObj = useRef<any>(null);
  const apiKey = (process.env.NEXT_PUBLIC_YANDEX_MAPS_API_KEY || "").trim();

  const latNum = useMemo(() => Number(props.latitude), [props.latitude]);
  const lngNum = useMemo(() => Number(props.longitude), [props.longitude]);

  useEffect(() => {
    if (!mapRef.current || initialized.current || !apiKey) return;

    const ensureScript = () =>
      new Promise<void>((resolve, reject) => {
        const existing = document.getElementById(SCRIPT_ID) as HTMLScriptElement | null;
        if (existing) {
          existing.addEventListener("load", () => resolve(), { once: true });
          if (window.ymaps) resolve();
          return;
        }
        const script = document.createElement("script");
        script.id = SCRIPT_ID;
        script.src = `https://api-maps.yandex.ru/2.1/?apikey=${encodeURIComponent(apiKey)}&lang=ru_RU`;
        script.async = true;
        script.onload = () => resolve();
        script.onerror = () => reject(new Error("Failed to load Yandex Maps"));
        document.body.appendChild(script);
      });

    ensureScript()
      .then(() => window.ymaps?.ready?.())
      .then(() => {
        if (!mapRef.current || initialized.current || !window.ymaps) return;
        initialized.current = true;
        const center =
          Number.isFinite(latNum) && Number.isFinite(lngNum) ? [latNum, lngNum] : [55.751244, 37.618423];
        mapObj.current = new window.ymaps.Map(mapRef.current, { center, zoom: 10, controls: ["zoomControl"] });
        mapObj.current.events.add("click", (e: any) => {
          const coords = e.get("coords");
          const lat = Number(coords[0]).toFixed(6);
          const lng = Number(coords[1]).toFixed(6);
          props.onLatitudeChange(lat);
          props.onLongitudeChange(lng);
          if (!markObj.current) {
            markObj.current = new window.ymaps.Placemark(coords, {}, { draggable: true });
            mapObj.current.geoObjects.add(markObj.current);
            markObj.current.events.add("dragend", () => {
              const c = markObj.current.geometry.getCoordinates();
              props.onLatitudeChange(Number(c[0]).toFixed(6));
              props.onLongitudeChange(Number(c[1]).toFixed(6));
            });
          } else {
            markObj.current.geometry.setCoordinates(coords);
          }
        });
      })
      .catch(() => {});
  }, [apiKey, latNum, lngNum, props]);

  useEffect(() => {
    if (!mapObj.current || !window.ymaps) return;
    if (!Number.isFinite(latNum) || !Number.isFinite(lngNum)) return;
    const coords = [latNum, lngNum];
    if (!markObj.current) {
      markObj.current = new window.ymaps.Placemark(coords, {}, { draggable: true });
      mapObj.current.geoObjects.add(markObj.current);
    } else {
      markObj.current.geometry.setCoordinates(coords);
    }
    mapObj.current.setCenter(coords, Math.max(mapObj.current.getZoom(), 12), { duration: 120 });
  }, [latNum, lngNum]);

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <input
          type="text"
          value={props.address}
          onChange={(e) => props.onAddressChange(e.target.value)}
          className="input sm:col-span-3"
          placeholder="Адрес объекта"
        />
        <input
          type="number"
          step="0.000001"
          value={props.latitude}
          onChange={(e) => props.onLatitudeChange(e.target.value)}
          className="input"
          placeholder="Широта"
        />
        <input
          type="number"
          step="0.000001"
          value={props.longitude}
          onChange={(e) => props.onLongitudeChange(e.target.value)}
          className="input"
          placeholder="Долгота"
        />
      </div>
      {apiKey ? (
        <div ref={mapRef} className="h-56 w-full overflow-hidden rounded-lg border border-surface-200" />
      ) : (
        <p className="text-xs text-surface-500">
          Для карты задайте `NEXT_PUBLIC_YANDEX_MAPS_API_KEY` в `.env`.
        </p>
      )}
    </div>
  );
}
