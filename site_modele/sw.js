// Version en ligne : on charge toujours la dernière version depuis Internet,
// et on garde une copie pour pouvoir consulter la dernière liste sans réseau.
const CACHE = "immo-site";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));

self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    fetch(e.request, { cache: "no-store" })
      .then(rep => {
        const copie = rep.clone();
        caches.open(CACHE).then(c => c.put(e.request, copie));
        return rep;
      })
      .catch(() => caches.match(e.request, { ignoreSearch: true }))
  );
});
