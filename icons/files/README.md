# Sale Petal 🌸

A clean beauty-sale tracker PWA. Add your favorite brands, tap one button, and it searches the web (Sephora, ULTA, Nordstrom, Macy's, brand sites) for current sales, gift-with-purchase, and promo codes. New deals since your last check get a glowing **New** badge.

Installs on your Android home screen like a real app. Sends push notifications when new deals are found. No app store needed.

---

## Project files
```
sale-petal/
├── index.html          ← the whole app
├── manifest.json       ← makes it installable as an app
├── service-worker.js   ← offline support + push notifications
├── icons/
│   ├── icon-192.png    ← app icon (home screen)
│   └── icon-512.png    ← app icon (splash screen)
└── README.md
```

---

## Run it locally

```bash
python3 -m http.server 8000
# visit http://localhost:8000/sale-petal/
```

> Note: service workers require either localhost or HTTPS. Won't fully work if you just double-click index.html.

---

## Get your Anthropic API key

1. Go to **console.anthropic.com** → API Keys → Create Key
2. Open the app, paste the key into the setup box, hit **Save**
3. Stored in your browser's localStorage only — never in the code

---

## Deploy to GitHub Pages

```bash
git init
git add .
git commit -m "Sale Petal PWA"
git branch -M main
git remote add origin https://github.com/ashleycanva/sale-petal.git
git push -u origin main
```

Then on GitHub: **Settings → Pages → Source: main / (root)**
Lives at: `https://ashleycanva.github.io/sale-petal/`

---

## Install on your Fold 7 (Android)

1. Open Chrome on your phone
2. Go to `https://ashleycanva.github.io/sale-petal/`
3. Tap the **⋮ menu → Add to Home Screen**
4. Tap **Install**
5. Sale Petal icon appears on your home screen — opens full screen, no browser bar
6. On first deal search, it'll ask to allow notifications — tap **Allow**

That's it. It works like a real app.

---

## Updating the app

Just push changes to GitHub — the phone picks them up automatically next time you open it. No reinstalling ever.

```bash
git add .
git commit -m "what I changed"
git push
```

---

## Working across two computers (work + home)

**At the start of every session — pull first:**
```bash
git pull
```

**At the end of every session — push before you leave:**
```bash
git add .
git commit -m "what I changed"
git push
```

Your API key is saved per-browser (localStorage), so paste it once on each computer. It's not in the code — that's intentional and keeps it safe.

---

## Ideas to build next (tell Claude Code in plain English)

- Sort deals by biggest discount
- Group deals by retailer tab (Sephora / ULTA / Nordstrom)
- Star/pin your favorite deals
- Set a % threshold — only show deals above X% off
- Custom app icon with your initials

---

Fonts: **Anton** (display) + **Archivo** (body)
Palette: warm cream `#F6F0E9` + clay `#C98B7A` + gold `#B79B6E`
