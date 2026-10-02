import { useEffect, useState } from "react";
import { api, type Brand } from "./api";

/**
 * The site name and icon. Nothing is written here on purpose: the values come from the server
 * (APP_NAME / APP_ICON in .env, or whatever the super-admin page saved), are remembered in
 * localStorage so the tab is right before the app loads, and are refreshed on every page load.
 */
const KEY = "brand";
const read = (): Brand => {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "");
    if (typeof v?.name === "string" && typeof v?.icon === "string") return v;
  } catch {
    /* nothing saved yet */
  }
  return { name: "", icon: "" };
};

let brand = read();
let page = "";
const listeners = new Set<() => void>();

function paint() {
  document.title = [page, brand.name].filter(Boolean).join(" · ") || location.host;
  const link = document.getElementById("icon") as HTMLLinkElement | null;
  if (link) link.href = brand.icon || "data:,";
}

/** Ask the server once per page load; keep the cached value if it can't be reached. */
export async function loadBrand() {
  try {
    const b = await api<Brand>("/api/brand");
    if (!b || (b.name === brand.name && b.icon === brand.icon)) return;
    brand = b;
    try {
      localStorage.setItem(KEY, JSON.stringify(b));
    } catch {
      /* private mode: just not remembered */
    }
    paint();
    listeners.forEach((f) => f());
  } catch {
    /* offline: the cached name and icon stay */
  }
}

export function useBrand(): Brand {
  const [, tick] = useState(0);
  useEffect(() => {
    const f = () => tick((n) => n + 1);
    listeners.add(f);
    return () => void listeners.delete(f);
  }, []);
  return brand;
}

/** Tab title: "<page> · <site name>", or just the site name when `part` is empty. */
export function usePageTitle(part = "") {
  useEffect(() => {
    page = part;
    paint();
  }, [part]);
}

/** Icon above the name, centered. Used on the login pages. */
export function BrandMark() {
  const b = useBrand();
  if (!b.icon && !b.name) return null;
  return (
    <div className="brand">
      {b.icon && <img src={b.icon} alt="" onError={(e) => (e.currentTarget.hidden = true)} />}
      {b.name && <h1>{b.name}</h1>}
    </div>
  );
}
