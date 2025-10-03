import "../styles/globals.css";
import React, { useEffect, useState } from "react";
import { useRouter } from "next/router";

export default function App({ Component, pageProps }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const publicPaths = ["/components/Login", "/components/Signup", "/forgot-password", "/"]; // add more if needed

    const hasToken = () => {
      if (typeof window === "undefined") return false;
      return Boolean(localStorage.getItem("access_token"));
    };

    const guard = (url) => {
      const path = typeof url === "string" ? url : router.asPath;
      const isPublic = publicPaths.some((p) => path === p || path.startsWith(`${p}?`));
      const authed = hasToken();

      if (!authed && !isPublic) {
        router.replace("/components/Login");
        return false;
      }
      if (authed && (path === "/components/Login" || path === "/components/Signup")) {
        router.replace("/components/DepartmentConfig");
        return false;
      }
      return true;
    };

    guard(router.asPath);
    setReady(true);

    const onStart = (url) => { guard(url); };
    router.events.on("routeChangeStart", onStart);

    const onStorage = (e) => {
      if (e.key === "access_token" && e.newValue === null) {
        router.replace("/components/Login");
      }
    };
    window.addEventListener("storage", onStorage);

    return () => {
      router.events.off("routeChangeStart", onStart);
      window.removeEventListener("storage", onStorage);
    };
  }, [router]);

  if (!ready) return null;

  return <Component {...pageProps} />;
}
