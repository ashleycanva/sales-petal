# Sale Petal 🌸

A clean beauty-sale tracker. Add your favorite brands, tap one button, and it searches the web (Sephora, ULTA, Nordstrom, Macy's, brand sites) for current sales, gift-with-purchase, and promo codes. New deals since your last check get a glowing **New** badge.

Single HTML file. No build step. Same deploy pattern as Sony CalTrack.

---

## What changed from the Claude.ai version

The chat/artifact version used two things that only work *inside* Claude.ai:

| Artifact version | This standalone version |
|---|---|
| `window.storage` | `localStorage` |
| Anthropic API call with no key (auto-auth) | You paste your own API key (saved in your browser) |

That's why this one works on GitHub Pages and the artifact one wouldn't.

---

## Run it locally

Just open `index.html` in a browser, or serve it:

```bash
python3 -m http.server 8000
# then visit http://localhost:8000
```

## Get your Anthropic API key

1. Go to **console.anthropic.com** → API Keys → Create Key
2. Open the app, paste the key into the one-time setup box, hit **Save**
3. It's stored in your browser's localStorage only — never in the code

> Note: the deal search uses Claude's **web search** tool, which is a paid API feature (small per-search cost). Check current pricing in the Anthropic console.

## Deploy to GitHub Pages

```bash
git init
git add .
git commit -m "Sale Petal: beauty sale tracker"
git branch -M main
git remote add origin https://github.com/ashleycanva/sale-petal.git
git push -u origin main
```

Then on GitHub: **Settings → Pages → Source: main branch → /(root)**.
Lives at `https://ashleycanva.github.io/sale-petal/`.

---

## Security note ⚠️

Your API key lives in *your* browser only. **Do not hard-code your key into `index.html`** if the repo is public — anyone could read it from the source. The paste-it-yourself setup keeps it safe.

## Ideas to build next (just ask Claude Code in plain English)

- Sort deals by biggest discount
- Group deals by retailer
- Set a target price per brand and only alert below it
- Add a "favorites" star to pin deals
- Swap the headline font to Archivo Expanded for a wider, Druk-style look

---

Fonts: **Anton** (display) + **Archivo** (body). Palette: warm cream + clay.
