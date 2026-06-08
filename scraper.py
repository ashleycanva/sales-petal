import requests
import json
import smtplib
import os
import re
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

BRANDS = ['lancome', 'lancôme', 'dr. jart', 'dr jart', 'hourglass', 'patrick ta', 'patrick ta beauty']
BRAND_DISPLAY = {
    'lancome': 'Lancôme', 'lancôme': 'Lancôme',
    'dr. jart': 'Dr. Jart+', 'dr jart': 'Dr. Jart+',
    'hourglass': 'Hourglass',
    'patrick ta': 'Patrick Ta', 'patrick ta beauty': 'Patrick Ta'
}
STORES = ['sephora', 'ulta', 'amazon', 'nordstrom', 'macys', 'macy']
EMAIL = 'thanhthanh12396@gmail.com'
SITE_URL = 'https://ashleycanva.github.io/sales-petal'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
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
    return (d.get('brand', '') + '|' + d.get('retailer', '') + '|' + d.get('title', '')).lower().strip()

def extract_discount(text):
    m = re.search(r'(\d+)\s*%\s*off', text, re.IGNORECASE)
    if m:
        return f'{m.group(1)}% off'
    m = re.search(r'\$(\d+)\s*off', text, re.IGNORECASE)
    if m:
        return f'${m.group(1)} off'
    if re.search(r'sale|deal|discount|promo|markdown|clearance', text, re.IGNORECASE):
        return 'On Sale'
    return 'Deal'

def extract_retailer(text):
    tl = text.lower()
    if 'sephora' in tl:
        return 'Sephora'
    if 'ulta' in tl:
        return 'Ulta'
    if 'amazon' in tl:
        return 'Amazon'
    if 'nordstrom' in tl:
        return 'Nordstrom'
    if 'macys' in tl or "macy's" in tl:
        return "Macy's"
    return 'Online'

# ── SlickDeals RSS (most reliable, no bot detection) ──────────────────────────
def scrape_slickdeals():
    if not HAS_FEEDPARSER:
        print('feedparser not available')
        return []

    deals = []
    queries = [
        ('lancome beauty', 'Lancôme'),
        ('dr jart', 'Dr. Jart+'),
        ('hourglass cosmetics', 'Hourglass'),
        ('patrick ta beauty', 'Patrick Ta'),
        ('sephora sale skincare', None),
        ('ulta sale makeup', None),
    ]

    seen = set()
    for query, brand_override in queries:
        try:
            url = f'https://slickdeals.net/newsearch.php?src=SearchBarV2&mode=frontpage&searcharea=deals&q={query.replace(" ", "+")}&rss=1'
            feed = feedparser.parse(url)
            print(f'  SlickDeals "{query}": {len(feed.entries)} entries')

            for entry in feed.entries[:8]:
                title = entry.get('title', '')
                link = entry.get('link', '')
                summary_html = entry.get('summary', '')
                summary = BeautifulSoup(summary_html, 'html.parser').get_text(separator=' ')[:200]
                full_text = title + ' ' + summary

                brand = brand_override
                if not brand:
                    brand = match_brand(full_text)
                if not brand:
                    continue

                retailer = extract_retailer(full_text)
                discount = extract_discount(full_text)
                uid = (brand + title).lower()
                if uid in seen:
                    continue
                seen.add(uid)

                deals.append({
                    'brand': brand,
                    'retailer': retailer,
                    'title': title[:80],
                    'discount': discount,
                    'details': summary[:100] if summary else '',
                    'url': link,
                    'image': '',
                    'validUntil': ''
                })
        except Exception as e:
            print(f'SlickDeals error for "{query}": {e}')

    return deals

# ── DealNews RSS ──────────────────────────────────────────────────────────────
def scrape_dealnews():
    if not HAS_FEEDPARSER:
        return []

    deals = []
    queries = ['lancome', 'dr+jart', 'hourglass+cosmetics', 'patrick+ta+beauty']

    for query in queries:
        try:
            url = f'https://www.dealnews.com/c196/Beauty-Personal-Care/?p=&q={query}&s=1'
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, 'html.parser')
            items = soup.select('article, .deal-item, [class*="deal"]')[:5]
            for item in items:
                title_el = item.select_one('h2, h3, .title, [class*="title"]')
                link_el = item.select_one('a[href]')
                price_el = item.select_one('.price, [class*="price"]')
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                brand = match_brand(title)
                if not brand:
                    continue
                href = link_el['href'] if link_el else ''
                if href and not href.startswith('http'):
                    href = 'https://www.dealnews.com' + href
                deals.append({
                    'brand': brand,
                    'retailer': extract_retailer(title),
                    'title': title[:80],
                    'discount': price_el.get_text(strip=True) if price_el else extract_discount(title),
                    'details': '',
                    'url': href,
                    'image': '',
                    'validUntil': ''
                })
        except Exception as e:
            print(f'DealNews error for {query}: {e}')

    return deals

# ── Sephora direct API ────────────────────────────────────────────────────────
def scrape_sephora():
    deals = []
    session = requests.Session()

    # Warm up session with a page visit
    try:
        session.get('https://www.sephora.com', headers=HEADERS, timeout=15)
    except Exception:
        pass

    brand_slugs = [
        ('lancome', 'Lancôme'),
        ('dr-jart', 'Dr. Jart+'),
        ('hourglass-cosmetics', 'Hourglass'),
        ('patrick-ta', 'Patrick Ta'),
    ]

    for slug, display in brand_slugs:
        try:
            url = (f'https://www.sephora.com/api/catalog/brands/{slug}/products'
                   f'?currentPage=1&pageSize=60&content=true&country=US&lang=en-US'
                   f'&sortBy=SALE&onSale=true')
            r = session.get(url, headers={**HEADERS, 'Accept': 'application/json',
                                          'Referer': 'https://www.sephora.com/'}, timeout=15)
            print(f'  Sephora {slug}: {r.status_code}')
            if r.status_code == 200:
                products = r.json().get('products', [])
                for p in products:
                    lp = p.get('currentSku', {}).get('listPrice', '')
                    sp = p.get('currentSku', {}).get('salePrice', '') or lp
                    if lp == sp:
                        continue
                    try:
                        pct = round((float(lp.replace('$','')) - float(sp.replace('$',''))) / float(lp.replace('$','')) * 100)
                        discount = f'{pct}% off' if pct > 0 else 'On Sale'
                    except Exception:
                        discount = 'On Sale'
                    deals.append({
                        'brand': display,
                        'retailer': 'Sephora',
                        'title': p.get('displayName', '')[:80],
                        'discount': discount,
                        'details': f'Was {lp} — now {sp}',
                        'url': 'https://www.sephora.com' + p.get('targetUrl', ''),
                        'image': p.get('heroImage', ''),
                        'validUntil': ''
                    })
        except Exception as e:
            print(f'  Sephora {slug} error: {e}')

    return deals

# ── Ulta direct ───────────────────────────────────────────────────────────────
def scrape_ulta():
    deals = []
    session = requests.Session()

    try:
        session.get('https://www.ulta.com', headers=HEADERS, timeout=15)
    except Exception:
        pass

    brand_slugs = [
        ('lancome', 'Lancôme'),
        ('dr-jart', 'Dr. Jart+'),
        ('hourglass-cosmetics', 'Hourglass'),
        ('patrick-ta', 'Patrick Ta'),
    ]

    for slug, display in brand_slugs:
        try:
            url = f'https://www.ulta.com/brand/{slug}?prefn1=isSaleOrPromo&prefv1=Sale'
            r = session.get(url, headers={**HEADERS, 'Referer': 'https://www.ulta.com/'}, timeout=20)
            print(f'  Ulta {slug}: {r.status_code}')
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, 'html.parser')
            cards = soup.select('.ProductCard, [class*="ProductCard"]')
            print(f'    Found {len(cards)} product cards')
            for card in cards[:8]:
                name_el = card.select_one('[class*="name"], [class*="Name"], h3, h4')
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
                    'title': name_el.get_text(strip=True)[:80],
                    'discount': sale_el.get_text(strip=True) if sale_el else 'On Sale',
                    'details': '',
                    'url': href,
                    'image': '',
                    'validUntil': ''
                })
        except Exception as e:
            print(f'  Ulta {slug} error: {e}')

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

    print('SlickDeals RSS...')
    sd = scrape_slickdeals()
    print(f'  {len(sd)} deals')
    all_deals.extend(sd)

    print('DealNews...')
    dn = scrape_dealnews()
    print(f'  {len(dn)} deals')
    all_deals.extend(dn)

    print('Sephora direct...')
    sep = scrape_sephora()
    print(f'  {len(sep)} deals')
    all_deals.extend(sep)

    print('Ulta direct...')
    ulta = scrape_ulta()
    print(f'  {len(ulta)} deals')
    all_deals.extend(ulta)

    # Deduplicate
    seen_ids = set()
    unique = []
    for d in all_deals:
        did = deal_id(d)
        if did not in seen_ids:
            seen_ids.add(did)
            unique.append(d)
    all_deals = unique
    print(f'Total unique: {len(all_deals)}')

    # Load previous
    try:
        with open('deals.json') as f:
            prev = json.load(f).get('deals', [])
    except Exception:
        prev = []

    prev_ids = {deal_id(d) for d in prev}
    new_deals = [d for d in all_deals if deal_id(d) not in prev_ids]
    print(f'New: {len(new_deals)}')

    with open('deals.json', 'w') as f:
        json.dump({
            'deals': all_deals,
            'updatedAt': datetime.utcnow().isoformat() + 'Z',
            'count': len(all_deals)
        }, f, indent=2)

    if new_deals:
        send_email(new_deals, len(all_deals))

    print('Done.')

if __name__ == '__main__':
    main()
