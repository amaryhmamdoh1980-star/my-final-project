self.addEventListener('install', (e) => {
  console.log('Service Worker Installed');
});

self.addEventListener('fetch', (e) => {
  // מאפשר לאפליקציה לעבוד אונליין
  e.respondWith(fetch(e.request));
});