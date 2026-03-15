self.addEventListener('install', (e) => {
  console.log('Service Worker: Installed');
});

self.addEventListener('fetch', (e) => {
  // כאן אפשר להוסיף יכולות אופליין בעתיד, כרגע זה רק לצורך הגדרת האפליקציה
  e.respondWith(fetch(e.request));
});
