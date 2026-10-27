"use strict";

self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (_) {
    const xml = event.data ? event.data.text() : "";
    const textos = [...xml.matchAll(/<text[^>]*>([\s\S]*?)<\/text>/gi)].map((match) =>
      match[1].replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&amp;/g, "&")
    );
    payload = xml.includes("<toast")
      ? { title: textos[0] || "Ahora Qué", body: textos[1] || "Tenés una novedad pendiente." }
      : { body: xml || "Tenés una novedad en Ahora Qué." };
  }

  const title = payload.title || "Ahora Qué";
  const options = {
    body: payload.body || "Tenés una novedad pendiente.",
    icon: "/static/apple-touch-icon.png",
    badge: "/static/apple-touch-icon.png",
    data: { url: payload.url || "/dashboard" },
    tag: payload.tag || "ahora-que-notificacion",
    renotify: false,
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const destino = new URL(event.notification.data?.url || "/dashboard", self.location.origin);
  const ruta = destino.origin === self.location.origin ? destino.href : new URL("/dashboard", self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientes) => {
      for (const cliente of clientes) {
        if (new URL(cliente.url).origin === self.location.origin) {
          cliente.navigate(ruta);
          return cliente.focus();
        }
      }
      return self.clients.openWindow(ruta);
    })
  );
});
