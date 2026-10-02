import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { Admin } from "./screens/Admin";
import { Clarifications } from "./screens/Clarifications";
import { Display } from "./screens/Display";
import { Login } from "./screens/Login";
import { Proctor } from "./screens/Proctor";
import { Super } from "./screens/Super";
import { loadBrand } from "./brand";

export function go(path: string) {
  history.pushState(null, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function App() {
  const [path, setPath] = useState(location.pathname);
  useEffect(() => {
    const f = () => setPath(location.pathname);
    window.addEventListener("popstate", f);
    return () => window.removeEventListener("popstate", f);
  }, []);
  if (path.startsWith("/admin/clarifications")) return <Clarifications />;
  if (path.startsWith("/admin")) return <Admin />;
  if (path.startsWith("/display")) return <Display />;
  if (path.startsWith("/proctor")) return <Proctor />;
  if (path.startsWith("/super")) return <Super />;
  return <Login />;
}

void loadBrand();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
