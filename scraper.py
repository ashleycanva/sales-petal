import requests
import json
import os
import re
from bs4 import BeautifulSoup
from datetime import datetime

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
}

def load_config():
    try:
        with open('user-config.json', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f'Could not load user-config.json: {e}')
        return {'products': [], 'brands': []}


# ── Brand: scrape homepage notification/announcement bar ──────────────────────

def scrape_notification_bar(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f'  HTTP {r.status_code} for {url}')
            return ''
        soup = BeautifulSoup(r.text, 'html.parser')

        for tag in soup(['script', 'style', 'noscript', 'footer', 'nav']):
            tag.decompose()

        selectors = [
            '[class*="announcement"]',
            '[class*="promo-bar"]',
            '[class*="notification-bar"]',
            '[class*="top-bar"]',
            '[class*="site-banner"]',
            '[class*="promo-banner"]',
            '[class*="header-banner"]',
            '[class*="marquee"]',
            '[class*="sitewide-banner"]',
            '[data-section-type="announcement-bar"]',
            '[id*="announcement"]',
            '[id*="promo-bar"]',
        ]

        texts = []
        seen = set()
        for sel in selectors:
            for el in soup.select(sel):
                t = el.get_text(separator=' ', strip=True)
                if t and len(t) > 5 and t[:60] not in seen:
                    texts.append(t)
                    seen.add(t[:60])

        if texts:
            combined = ' | '.join(texts[:5])
            print(f'  Bar ({len(texts)} elements): {combined[:120]}')
            return combined

        # Fallback: grab first 600 chars of body text above the fold
        body = soup.find('body')
        if body:
            text = body.get_text(separator=' ', strip=True)[:600]
            print(f'  Fallback body text: {text[:80]}')
            return text

        return ''
    except Exception as e:
        print(f'  Notification bar error for {url}: {e}')
        return ''


def extract_brand_deals_claude(client, brand_name, bar_text, brand_url):
    if not bar_text or not bar_text.strip():
        return {'has_deals': False, 'deals': [], 'summary': ''}
    try:
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=600,
            messages=[{
                'role': 'user',
                'content': (
                    'Extract active promotions from this text scraped from ' + brand_name +
                    ' website (' + brand_url + ').\n\n'
                    'Text: ' + bar_text[:1200] + '\n\n'
                    'Return JSON only, no other text:\n'
                    '{\n'
                    '  "has_deals": true or false,\n'
                    '  "deals": [\n'
                    '    {\n'
                    '      "text": "short deal description",\n'
                    '      "type": "promo_code|bogo|gwp|sale_event|free_shipping|other",\n'
                    '      "code": "CODENAME or null",\n'
                    '      "discount": "20% off or null",\n'
                    '      "expiry": "date string or null"\n'
                    '    }\n'
                    '  ],\n'
                    '  "summary": "one-line summary of the best active deal"\n'
                    '}\n\n'
                    'Include: promo codes, BOGO, GWP (gift with purchase), sale events, '
                    'free shipping thresholds. '
                    'Set has_deals to false if there are only new product announcements '
                    'with no discount or promotion.'
                )
            }]
        )
        raw = msg.content[0].text.strip()
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        return json.loads(match.group() if match else raw)
    except Exception as e:
        print(f'  Claude brand error for {brand_name}: {e}')
        return {'has_deals': False, 'deals': [], 'summary': ''}


# ── Product: search Sephora and Ulta ─────────────────────────────────────────

def search_sephora(product_name):
    try:
        q = requests.utils.quote(product_name)
        url = (
            'https://www.sephora.com/api/catalog/search'
            '?q=' + q + '&pageSize=5&currentPage=1&country=US&lang=en-US'
        )
        r = requests.get(url, headers={
            **HEADERS,
            'Accept': 'application/json',
            'Referer': 'https://www.sephora.com/',
        }, timeout=15)
        print(f'  Sephora HTTP {r.status_code}')
        if r.status_code != 200:
            return None
        products = r.json().get('products', [])
        if not products:
            return None
        p = products[0]
        sku = p.get('currentSku', {})
        list_price = sku.get('listPrice', '') or ''
        sale_price = sku.get('salePrice', '') or ''
        on_sale = bool(sale_price and sale_price != list_price)
        discount = None
        if on_sale and list_price and sale_price:
            try:
                lp = float(list_price.replace('$', ''))
                sp = float(sale_price.replace('$', ''))
                pct = round((lp - sp) / lp * 100)
                discount = str(pct) + '% off'
            except Exception:
                discount = 'On Sale'
        return {
            'retailer': 'Sephora',
            'on_sale': on_sale,
            'original_price': list_price,
            'sale_price': sale_price if on_sale else None,
            'discount': discount,
            'url': 'https://www.sephora.com' + p.get('targetUrl', ''),
        }
    except Exception as e:
        print(f'  Sephora error for "{product_name}": {e}')
        return None


def search_ulta(product_name):
    try:
        q = requests.utils.quote(product_name)
        url = 'https://www.ulta.com/search?query=' + q
        r = requests.get(url, headers=HEADERS, timeout=15)
        print(f'  Ulta HTTP {r.status_code}')
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')
        card = soup.select_one('[class*="ProductCard"], [class*="product-item"]')
        if not card:
            return None
        link_el = card.select_one('a[href]')
        price_el = card.select_one('[class*="regular"], [class*="Price--regular"]')
        sale_el = card.select_one('[class*="sale"], [class*="Price--sale"]')
        href = link_el['href'] if link_el else ''
        if href and not href.startswith('http'):
            href = 'https://www.ulta.com' + href
        on_sale = bool(sale_el and sale_el.get_text(strip=True))
        return {
            'retailer': 'Ulta',
            'on_sale': on_sale,
            'original_price': price_el.get_text(strip=True) if price_el else None,
            'sale_price': sale_el.get_text(strip=True) if on_sale and sale_el else None,
            'discount': 'On Sale' if on_sale else None,
            'url': href,
        }
    except Exception as e:
        print(f'  Ulta error for "{product_name}": {e}')
        return None


def search_nordstrom(product_name):
    try:
        q = requests.utils.quote(product_name)
        url = 'https://www.nordstrom.com/sr?origin=keywordsearch&keyword=' + q
        r = requests.get(url, headers=HEADERS, timeout=15)
        print(f'  Nordstrom HTTP {r.status_code}')
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')
        card = soup.select_one('[class*="product-"], [class*="Product"]')
        if not card:
            return None
        link_el = card.select_one('a[href]')
        price_el = card.select_one('[class*="price"], [class*="Price"]')
        href = link_el['href'] if link_el else ''
        if href and not href.startswith('http'):
            href = 'https://www.nordstrom.com' + href
        price_text = price_el.get_text(strip=True) if price_el else ''
        on_sale = bool(re.search(r'\$.*\$', price_text))  # two prices = sale
        return {
            'retailer': 'Nordstrom',
            'on_sale': on_sale,
            'original_price': price_text.split()[0] if price_text else None,
            'sale_price': price_text.split()[-1] if on_sale and price_text else None,
            'discount': 'On Sale' if on_sale else None,
            'url': href,
        }
    except Exception as e:
        print(f'  Nordstrom error for "{product_name}": {e}')
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print('Sale Petal scraper starting at ' + datetime.now().isoformat())
    config = load_config()

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    client = None
    if api_key and HAS_ANTHROPIC:
        client = anthropic.Anthropic(api_key=api_key)
        print('Anthropic Haiku ready')
    else:
        print('No Anthropic API key or library — brand parsing will use raw text')

    # ── Section 1: Brand notification bars ────────────────────────────────
    brands_in = config.get('brands', [])
    print('\n=== BRANDS (' + str(len(brands_in)) + ') ===')
    brand_results = []
    brand_promo_map = {}  # brand name (lowercase) -> summary string

    for brand in brands_in:
        name = brand.get('name', '')
        url = brand.get('url', '')
        print('\nBrand: ' + name + ' (' + url + ')')

        bar_text = scrape_notification_bar(url) if url else ''

        if client and bar_text:
            data = extract_brand_deals_claude(client, name, bar_text, url)
        else:
            data = {
                'has_deals': bool(bar_text),
                'deals': [],
                'summary': bar_text[:200] if bar_text else '',
            }

        result = {
            'name': name,
            'url': url,
            'has_deals': data.get('has_deals', False),
            'deals': data.get('deals', []),
            'summary': data.get('summary', ''),
        }
        brand_results.append(result)
        print('  has_deals=' + str(result['has_deals']) + ' summary=' + result['summary'][:80])

        if result['has_deals'] and result['summary']:
            brand_promo_map[name.lower()] = result['summary']

    # ── Section 2: Product searches ────────────────────────────────────────
    products_in = config.get('products', [])
    print('\n=== PRODUCTS (' + str(len(products_in)) + ') ===')
    product_results = []

    for product in products_in:
        name = product.get('name', '')
        brand = product.get('brand', '')
        print('\nProduct: ' + name + ' (brand: ' + brand + ')')

        sephora = search_sephora(name)
        ulta = search_ulta(name)
        nordstrom = search_nordstrom(name)

        retailers = [r for r in [sephora, ulta, nordstrom] if r]
        on_sale = any(r['on_sale'] for r in retailers)

        # Cross-reference: does this product's brand have an active promo?
        brand_promo = brand_promo_map.get(brand.lower())

        product_results.append({
            'name': name,
            'brand': brand,
            'on_sale': on_sale,
            'retailers': retailers,
            'brand_promo_alert': brand_promo,
        })
        status = 'ON SALE' if on_sale else ('brand promo' if brand_promo else 'no deals')
        print('  -> ' + status)

    # ── Write deals.json ───────────────────────────────────────────────────
    output = {
        'products': product_results,
        'brands': brand_results,
        'updatedAt': datetime.utcnow().isoformat() + 'Z',
    }

    with open('deals.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print('\nDone. ' + str(len(product_results)) + ' products, ' + str(len(brand_results)) + ' brands.')


if __name__ == '__main__':
    main()
