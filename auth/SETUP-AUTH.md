# Vault Fantasy — Cross-device login setup (Google + email/password)

Your repo gets **3 new files** plus the updated `index.html`:

```
Vault-Fantasy3/
├─ index.html              ← REPLACE (adds 3 auth lines in <head>; inert until configured)
├─ login.html              ← ADD (the sign-in page)
└─ auth/
   ├─ firebase-config.js   ← ADD (you paste your Firebase config here)
   ├─ vault-auth.js        ← ADD (auth + sync engine)
   └─ SETUP-AUTH.md        ← this file
```

**Safe rollout:** until you paste a config into `auth/firebase-config.js`, the site
behaves EXACTLY as today — no login screen, no redirects. You can upload all files
first and configure later.

---

## Firebase setup (~10 min, free — no card required)

### 1. Create the project
1. Go to **console.firebase.google.com** → *Add project*
2. Name it (e.g. `vault-fantasy`) → Google Analytics: **off** is fine → *Create*

### 2. Enable sign-in providers
1. Left sidebar: **Build → Authentication** → *Get started*
2. **Sign-in method** tab:
   - Enable **Google** (pick your support email) → Save
   - Enable **Email/Password** → Save

### 3. Authorize your domain
1. Authentication → **Settings** tab → **Authorized domains**
2. *Add domain* → your GitHub Pages domain, e.g. `YOURUSERNAME.github.io`
   (localhost is pre-authorized for local testing)

### 4. Create the database
1. **Build → Firestore Database** → *Create database*
2. Location: `nam5 (us-central)` is fine → **Production mode** → Create
3. **Rules** tab → replace everything with:

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{uid}/{document=**} {
      allow read, write: if request.auth != null && request.auth.uid == uid;
    }
  }
}
```
→ **Publish**. (Each user can read/write only their own data.)

### 5. Get your config
1. Gear icon → **Project settings** → *General* → scroll to **Your apps**
2. Click the **`</>`** (Web) icon → nickname `vault-web` → *Register app*
   (no need for Firebase Hosting)
3. Copy the `firebaseConfig = { ... }` object it shows you
4. Open `auth/firebase-config.js` and replace `null`:

```js
window.VF_FIREBASE_CONFIG = {
  apiKey: "AIzaSy...",
  authDomain: "vault-fantasy.firebaseapp.com",
  projectId: "vault-fantasy",
  storageBucket: "vault-fantasy.appspot.com",
  messagingSenderId: "123456789",
  appId: "1:123456789:web:abc123"
};
```

### 6. Upload to GitHub & bust the cache
1. Upload `login.html`, the `auth/` folder, and the new `index.html`
2. **Important:** your `sw.js` caches aggressively — bump the cache version
   string inside `sw.js` (or do a hard refresh) so the new build shows up

---

## How it works after setup

- Visiting the site signed-out → redirected to `login.html`
- **Continue with Google** → popup → signed in. Email/password also works
  (Create account tab; password reset email built in)
- On sign-in, everything saved on your other devices is pulled down
  (rankings, watchlist, notes, trade-calc settings, Sleeper connection, theme),
  then the app opens — already set up
- While you use the app, every save is mirrored to the cloud automatically
  (debounced ~2s); other devices receive it live
- **"Skip for now — use this device only"** keeps today's localStorage-only
  behavior (sets a `vf-guest` flag; signing in later merges that work up)

### Sync details
- Keys synced: `snapdraft-*`, `dcmd-*`, `vault-*`, `lc-*`
- Conflict rule: per-key, newest write wins
- Free tier limits (Spark): 50K reads / 20K writes per day — a solo user
  won't get near them

### Not included yet (ask when you want them)
- Account chip + sign-out button inside the app header
- Apple sign-in (skipped — requires $99/yr Apple Developer Program)
