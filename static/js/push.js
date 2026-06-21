/* Notifications push PCS Live — abonnement Web Push + suivi par course.
   Composant Alpine `raceFollow(slug, year)` utilisé par le bouton « Suivre ». */
(function () {
  function urlB64ToUint8Array(base64) {
    const padding = '='.repeat((4 - (base64.length % 4)) % 4);
    const b64 = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = atob(b64);
    return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
  }

  async function getRegistration() {
    if (!('serviceWorker' in navigator)) return null;
    return navigator.serviceWorker.ready;
  }

  async function currentSubscription() {
    const reg = await getRegistration();
    return reg ? reg.pushManager.getSubscription() : null;
  }

  async function ensureSubscription() {
    // Renvoie un objet PushSubscription (en s'abonnant si nécessaire), ou null.
    const reg = await getRegistration();
    if (!reg || !('PushManager' in window)) return null;
    let sub = await reg.pushManager.getSubscription();
    if (sub) return sub;

    const cfg = await fetch('/api/push/config/').then((r) => r.json());
    if (!cfg.enabled || !cfg.public_key) return null;

    if (Notification.permission !== 'granted') {
      const perm = await Notification.requestPermission();
      if (perm !== 'granted') return null;
    }
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlB64ToUint8Array(cfg.public_key),
    });
    await fetch('/api/push/subscribe/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subscription: sub }),
    });
    return sub;
  }

  window.raceFollow = function (slug, year) {
    return {
      slug: slug,
      year: year,
      supported: 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window,
      enabled: true,        // push activé côté serveur (clés VAPID présentes)
      following: false,
      busy: false,
      denied: false,

      async init() {
        if (!this.supported) return;
        this.denied = (window.Notification && Notification.permission === 'denied');
        try {
          const sub = await currentSubscription();
          const ep = sub ? encodeURIComponent(sub.endpoint) : '';
          const q = `?slug=${encodeURIComponent(this.slug)}&year=${this.year}&endpoint=${ep}`;
          const r = await fetch('/api/push/following/' + q).then((x) => x.json());
          this.enabled = r.enabled;
          this.following = r.following;
        } catch (e) { /* silencieux */ }
      },

      get label() {
        if (!this.supported) return 'Non supporté';
        if (this.denied) return 'Notifs bloquées';
        if (this.busy) return '…';
        return this.following ? 'Suivi ✓' : 'Suivre';
      },

      async toggle() {
        if (!this.supported || this.busy) return;
        this.busy = true;
        try {
          const sub = await ensureSubscription();
          if (!sub) {
            this.denied = (window.Notification && Notification.permission === 'denied');
            this.busy = false;
            return;
          }
          const want = !this.following;
          const r = await fetch('/api/push/follow/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ subscription: sub, slug: this.slug, year: this.year, follow: want }),
          }).then((x) => x.json());
          this.following = r.following;
        } catch (e) { /* silencieux */ }
        this.busy = false;
      },
    };
  };
})();
