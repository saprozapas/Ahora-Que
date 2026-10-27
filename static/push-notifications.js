"use strict";

(() => {
  const endpoint = "/notificaciones/push/suscripciones";

  function actualizarCampos(form, modo) {
    form.elements.mail_activo.value = modo === "mail" ? "on" : "";
    form.elements.dispositivo_activo.value = modo === "dispositivo" ? "on" : "";
  }

  function restaurarModo(form) {
    const modo = form.dataset.currentMode || "apagadas";
    form.querySelectorAll('input[name="modo_notificaciones"]').forEach((radio) => {
      radio.checked = radio.value === modo;
    });
  }

  function base64UrlABytes(base64Url) {
    const padding = "=".repeat((4 - (base64Url.length % 4)) % 4);
    const base64 = (base64Url + padding).replace(/-/g, "+").replace(/_/g, "/");
    const raw = window.atob(base64);
    return Uint8Array.from(raw, (character) => character.charCodeAt(0));
  }

  function esAppIOSAgregada() {
    const ios = /iPhone|iPad|iPod/.test(navigator.userAgent)
      || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    return !ios || navigator.standalone === true || window.matchMedia("(display-mode: standalone)").matches;
  }

  async function quitarSuscripcionLocalYServidor() {
    const registro = await navigator.serviceWorker.getRegistration("/");
    const suscripcion = registro && await registro.pushManager.getSubscription();
    if (!suscripcion) return;
    try {
      await fetch(endpoint, {
        method: "DELETE",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ endpoint: suscripcion.endpoint }),
      });
    } finally {
      await suscripcion.unsubscribe();
    }
  }

  async function activarDispositivo(form) {
    const clavePublica = form.dataset.vapidPublicKey;
    if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
      throw new Error("Este navegador no admite notificaciones push.");
    }
    if (!esAppIOSAgregada()) {
      throw new Error("En iPhone o iPad, primero agregá Ahora Qué a Inicio y abrila desde su ícono.");
    }
    if (!clavePublica) {
      throw new Error("Falta configurar la clave pública VAPID en el servidor.");
    }

    // El permiso se solicita directamente como consecuencia de la elección de la persona.
    const permiso = Notification.permission === "granted"
      ? "granted"
      : await Notification.requestPermission();
    if (permiso !== "granted") {
      throw new Error("No se habilitó el permiso para mostrar notificaciones.");
    }

    const registro = await navigator.serviceWorker.register("/service-worker.js", { scope: "/" });
    let suscripcion = await registro.pushManager.getSubscription();
    if (!suscripcion) {
      suscripcion = await registro.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: base64UrlABytes(clavePublica),
      });
    }

    const respuesta = await fetch(endpoint, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subscription: suscripcion.toJSON() }),
    });
    const resultado = await respuesta.json().catch(() => ({}));
    if (!respuesta.ok) {
      throw new Error(resultado.error || "No se pudo registrar este dispositivo.");
    }
  }

  window.activarCanalNotificaciones = async (radio) => {
    const form = radio.form;
    const nuevoModo = radio.value;
    if (nuevoModo === "dispositivo") {
      try {
        await activarDispositivo(form);
      } catch (error) {
        window.alert(error.message || "No se pudieron activar las notificaciones en este dispositivo.");
        restaurarModo(form);
        return;
      }
    } else if (form.elements.dispositivo_activo.value === "on") {
      try {
        await quitarSuscripcionLocalYServidor();
      } catch (error) {
        console.warn("No se pudo quitar la suscripción local de push:", error);
      }
    }

    actualizarCampos(form, nuevoModo);
    form.dataset.currentMode = nuevoModo;
    form.submit();
  };
})();
