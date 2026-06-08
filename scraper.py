import requests
import json
import smtplib
import os
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

BRANDS = ['lancome', 'lancôme', 'dr. jart', 'dr jart', 'hourglass', 'patrick ta', 'patrick ta beauty']
BRAND_DISPLAY = {
    'lancome': 'Lancôme', 'lancôme': 'Lancôme',
    'dr. jart': 'Dr. Jart+', 'dr jart': 'Dr. Jart+',
    'hourglass': 'Hourglass',
    'patrick ta': 'Patrick Ta', 'patrick ta beauty': 'Patrick Ta'
}
EMAIL = 'thanhthanh12396@gmail.com'
SITE_URL = 'https://ashleycanva.github.io/sales-petal'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
}

def match_brand(text):
    if not text:
        return None
    tl = text.lower()
    for b in BRANDS:
        if b in tl:
            return BRAND_DISPLAY.get(b, b.title())
    return None

def deal_id(d):
    return (d.get('brand','') + '|' + d.get('retailer','') + '|' + d.get('title','')).lower().strip()

# ── Sephora ────────────────────────────────────────────────────────────────────
def scrape_sephora():
    deals = []
    try:
        url = ('https://www.sephora.com/api/catalog/categories/sale/products'
               '?currentPage=1&pageSize=100&content=true&country=US&lang=en-US&includeRegionsMap=true')
        r = requests.get(url, headers={**HEADERS, 'Accept': 'application/json'}, timeout=20)
        if r.status_code == 200:
            products = r.json().get('products', [])
            for p in products:
                brand_name = p.get('brand', {}).get('displayName', '')
                matched = match_brand(brand_name)
                if not matched:
                    continue
                lp = p.get('currentSku', {}).get('listPrice', '')
                sp = p.get('currentSku', {}).get('salePrice', '') or lp
                discount = ''
                try:
                    pct = round((float(lp.replace('$','')) - float(sp.replace('$',''))) / float(lp.replace('$','')) * 100)
                    if pct > 0:
                        discount = f'{pct}% off'
                except Exception:
                    pass
                deals.append({
                    'brand': matched,
                    'retailer': 'Sephora',
                    'title': p.get('displayName', ''),
                    'discount': discount or 'On Sale',
                    'details': f'Was {lp} — now {sp}' if lp and sp and lp != sp else '',
                    'url': 'https://www.sephora.com' + p.get('targetUrl', ''),
                    'image': p.get('heroImage', ''),
                    'validUntil': ''
                })
        else:
            print(f'Sephora API: {r.status_code}')
    except Exception as e:
        print(f'Sephora error: {e}')

    # Fallback: brand-specific sale pages
    if not deals:
        for brand_slug, brand_name in [('lancome', 'Lancôme'), ('dr-jart', 'Dr. Jart+'),
                                        ('hourglass', 'Hourglass'), ('patrick-ta', 'Patrick Ta')]:
            try:
                url = f'https://www.sephora.com/brand/{brand_slug}?currentPage=1&pageSize=60&sortBy=SALE'
                r = requests.get(url, headers={**HEADERS, 'Accept': 'application/json'}, timeout=20)
                if r.status_code == 200:
                    data = r.json()
                    for p in data.get('products', []):
                        lp = p.get('currentSku', {}).get('listPrice', '')
                        sp = p.get('currentSku', {}).get('salePrice', '') or lp
                        if lp == sp:
                            continue
                        deals.append({
                            'brand': brand_name,
                            'retailer': 'Sephora',
                            'title': p.get('displayName', ''),
                            'discount': 'On Sale',
                            'details': f'Was {lp} — now {sp}',
                            'url': 'https://www.sephora.com' + p.get('targetUrl', ''),
                            'image': p.get('heroImage', ''),
                            'validUntil': ''
                        })
            except Exception as e:
                print(f'Sephora brand {brand_slug} error: {e}')
    return deals

# ── Ulta ──────────────────────────────────────────────────────────────────────
def scrape_ulta():
    deals = []
    brand_slugs = [
        ('lancome', 'Lancôme'),
        ('dr-jart', 'Dr. Jart+'),
        ('hourglass-cosmetics', 'Hourglass'),
        ('patrick-ta', 'Patrick Ta'),
    ]
    for slug, display in brand_slugs:
        try:
            url = f'https://www.ulta.com/brand/{slug}?prefn1=isSaleOrPromo&prefv1=Sale'
            r = requests.get(url, headers={**HEADERS, 'Accept': 'text/html'}, timeout=20)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, 'html.parser')
            cards = soup.select('.ProductCard, [class*="product-card"], [class*="ProductCard"]')
            for card in cards[:10]:
                name_el = card.select_one('[class*="ProductCard-name"], [class*="product-name"], h3')
                sale_el = card.select_one('[class*="sale"], [class*="Sale"]')
                link_el = card.select_one('a[href]')
                if not name_el:
                    continue
                href = link_el['href'] if link_el else ''
                if href and not href.startswith('http'):
                    href = 'https://www.ulta.com' + href
                deals.append({
                    'brand': display,
                    'retailer': 'Ulta',
                    'title': name_el.get_text(strip=True),
                    'discount': sale_el.get_text(strip=True) if sale_el else 'On Sale',
                    'details': '',
                    'url': href,
                    'image': '',
                    'validUntil': ''
                })
        except Exception as e:
            print(f'Ulta {slug} error: {e}')
    return deals

# ── Amazon ────────────────────────────────────────────────────────────────────
def scrape_amazon():
    deals = []
    searches = [
        ('Lancome beauty sale', 'Lancôme'),
        ('Dr Jart beauty sale', 'Dr. Jart+'),
        ('Hourglass cosmetics sale', 'Hourglass'),
        ('Patrick Ta beauty sale', 'Patrick Ta'),
    ]
    for query, display in searches:
        try:
            url = f'https://www.amazon.com/s?k={query.replace(" ", "+")}&s=price-asc-rank'
            r = requests.get(url, headers={**HEADERS, 'Accept': 'text/html'}, timeout=20)
            if r.status_code != 200 or 'robot' in r.text[:500].lower():
                continue
            soup = BeautifulSoup(r.text, 'html.parser')
            items = soup.select('[data-component-type="s-search-result"]')[:3]
            for item in items:
                name_el = item.select_one('h2 span')
                price_el = item.select_one('.a-price .a-offscreen')
                badge_el = item.select_one('.a-badge-text, [class*="savingsPercentage"]')
                link_el = item.select_one('h2 a[href]')
                if not name_el:
                    continue
                href = link_el['href'] if link_el else ''
                if href and not href.startswith('http'):
                    href = 'https://www.amazon.com' + href
                deals.append({
                    'brand': display,
                    'retailer': 'Amazon',
                    'title': name_el.get_text(strip=True)[:80],
                    'discount': badge_el.get_text(strip=True) if badge_el else 'Deal',
                    'details': price_el.get_text(strip=True) if price_el else '',
                    'url': href,
                    'image': '',
                    'validUntil': ''
                })
        except Exception as e:
            print(f'Amazon {display} error: {e}')
    return deals

# ── Email ─────────────────────────────────────────────────────────────────────
def send_email(new_deals, total_count):
    pw = os.environ.get('GMAIL_APP_PASSWORD', '')
    if not pw:
        print('GMAIL_APP_PASSWORD not set — skipping email')
        return
    try:
        cards_html = ''
        for d in new_deals:
            cards_html += f'''
            <div style="background:#FCF9F5;border:1px solid #E3D6C7;border-radius:12px;padding:16px;margin-bottom:12px;border-left:3px solid #C98B7A;">
              <div style="font-size:18px;font-weight:800;color:#2B2724;font-family:Arial,sans-serif;">{d["brand"]}</div>
              <span style="display:inline-block;background:#F4E6DD;color:#C98B7A;font-size:12px;font-weight:700;padding:3px 10px;border-radius:20px;margin:5px 0;">{d["discount"]}</span>
              <div style="font-size:13px;color:#2B2724;margin:4px 0;">{d.get("title","")}</div>
              <div style="font-size:12px;color:#6E6259;">{d.get("details","")}</div>
              <div style="margin-top:10px;border-top:1px solid #E3D6C7;padding-top:8px;display:flex;justify-content:space-between;">
                <span style="font-size:11px;text-transform:uppercase;letter-spacing:.15em;color:#6E6259;">{d.get("retailer","")}</span>
                <a href="{d.get("url","#")}" style="font-size:12px;color:#C98B7A;font-weight:700;text-decoration:none;">View Deal →</a>
              </div>
            </div>'''

        html = f'''<div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;background:#F6F0E9;padding:28px 22px;border-radius:16px;">
          <div style="text-align:center;margin-bottom:24px;">
            <div style="font-size:11px;letter-spacing:.4em;text-transform:uppercase;color:#C98B7A;font-weight:600;">Curated Beauty Sales</div>
            <div style="font-size:44px;font-weight:900;color:#2B2724;line-height:1;">SALE <span style="color:#C98B7A;">PETAL</span></div>
          </div>
          <p style="color:#6E6259;font-size:14px;margin-bottom:20px;">
            🌸 <strong>{len(new_deals)} new deal{"s" if len(new_deals)!=1 else ""}</strong> just dropped for your tracked brands:
          </p>
          {cards_html}
          <div style="text-align:center;margin-top:24px;">
            <a href="{SITE_URL}" style="background:linear-gradient(135deg,#C98B7A,#B5704F);color:white;padding:14px 28px;border-radius:12px;text-decoration:none;font-weight:700;font-size:14px;letter-spacing:.05em;text-transform:uppercase;display:inline-block;">
              View All {total_count} Deals →
            </a>
          </div>
          <p style="text-align:center;font-size:11px;color:#BCAE9F;margin-top:20px;">
            Sale Petal checks every 4 hours · Confirm prices on the retailer's site before buying.
          </p>
        </div>'''

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'🌸 Sale Petal — {len(new_deals)} new deal{"s" if len(new_deals)!=1 else ""} found!'
        msg['From'] = EMAIL
        msg['To'] = EMAIL
        msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(EMAIL, pw)
            s.sendmail(EMAIL, EMAIL, msg.as_string())
        print(f'Email sent: {len(new_deals)} new deals')
    except Exception as e:
        print(f'Email error: {e}')

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f'Starting scrape at {datetime.now().isoformat()}')

    all_deals = []
    for fn, name in [(scrape_sephora, 'Sephora'), (scrape_ulta, 'Ulta'), (scrape_amazon, 'Amazon')]:
        print(f'Scraping {name}...')
        found = fn()
        print(f'  {len(found)} deals found')
        all_deals.extend(found)

    # Deduplicate by ID
    seen_ids = set()
    unique = []
    for d in all_deals:
        did = deal_id(d)
        if did not in seen_ids:
            seen_ids.add(did)
            unique.append(d)
    all_deals = unique

    # Load previous
    try:
        with open('deals.json') as f:
            prev = json.load(f).get('deals', [])
    except Exception:
        prev = []

    prev_ids = {deal_id(d) for d in prev}
    new_deals = [d for d in all_deals if deal_id(d) not in prev_ids]
    print(f'Total: {len(all_deals)} | New: {len(new_deals)}')

    with open('deals.json', 'w') as f:
        json.dump({'deals': all_deals, 'updatedAt': datetime.utcnow().isoformat() + 'Z', 'count': len(all_deals)}, f, indent=2)

    if new_deals:
        send_email(new_deals, len(all_deals))

    print('Done.')

if __name__ == '__main__':
    main()
