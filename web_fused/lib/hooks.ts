"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ApiError, getJson } from "./api";

export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(Boolean(path));
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<number | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!path) {
      setLoading(false);
      return;
    }
    const ctrl = new AbortController();
    let alive = true;
    setLoading(true);
    setError(null);
    getJson<T>(path, { signal: ctrl.signal })
      .then((json) => {
        if (!alive) return;
        setData(json);
        setStatus(200);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (!alive) return;
        if (err instanceof DOMException && err.name === "AbortError") return;
        const statusCode = err instanceof ApiError ? err.status : 0;
        setStatus(statusCode);
        setError(err instanceof Error ? err.message : "Request failed");
        setLoading(false);
      });
    return () => {
      alive = false;
      ctrl.abort();
    };
  }, [path, tick]);

  const reload = useCallback(() => setTick((n) => n + 1), []);
  return { data, loading, error, status, reload };
}

export function useFilters() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const get = useCallback(
    (key: string, fallback = "") => searchParams.get(key) ?? fallback,
    [searchParams],
  );

  const setMany = useCallback(
    (updates: Record<string, string | number | undefined | null>, resetOffset = true) => {
      const next = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value === undefined || value === null || value === "") next.delete(key);
        else next.set(key, String(value));
      }
      if (resetOffset && !("offset" in updates)) next.delete("offset");
      const qs = next.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  const set = useCallback(
    (key: string, value: string | number | undefined | null) => setMany({ [key]: value }),
    [setMany],
  );

  return { get, set, setMany, searchParams };
}

export function useDebounced<T>(value: T, delay = 280): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

export function useOffsetLimit() {
  const { get } = useFilters();
  return useMemo(
    () => ({
      limit: Math.min(200, Math.max(1, Number(get("limit", "25")) || 25)),
      offset: Math.max(0, Number(get("offset", "0")) || 0),
    }),
    [get],
  );
}
