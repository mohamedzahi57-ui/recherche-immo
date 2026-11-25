// Service worker minimal : il permet au téléphone d'« installer » l'application
// (icône sur l'écran d'accueil, plein écran). Les pages sont toujours chargées
// depuis le PC pour afficher les annonces à jour ; si le PC est injoignable,
// on affiche un petit message au lieu d'une erreur.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (e) => {
  if (e.request.mode !== "navigate") return;
  e.respondWith(
    fetch(e.request).catch(() => new Response(
      "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>" +
      "<body style='font-family:sans-serif;padding:24px'><h2>🏠 Recherche immo</h2>" +
      "<p>Le PC n'est pas joignable pour le moment.</p>" +
      "<p>Vérifiez que le PC est allumé et que Tailscale est activé sur le téléphone, puis réessayez.</p></body>",
      {headers: {"Content-Type": "text/html; charset=utf-8"}}))
  );
});
