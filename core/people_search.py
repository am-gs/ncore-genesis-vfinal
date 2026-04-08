"""NCore Genesis — People Search Scraper v1.0

Scrapes free public records sites using Playwright (Firefox, stealth mode).
Extracts: names, ages, addresses, phone numbers, relatives, property records.

Sites: TruePeopleSearch, FastPeopleSearch, ThatsThem, county assessors.
"""
from __future__ import annotations
import asyncio, re, time, random
import structlog

log = structlog.get_logger()

# Stealth JS injection for vanilla Playwright (when Camoufox unavailable)
_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
window.chrome = {runtime: {}};
"""

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"


async def _get_browser():
    """Launch Playwright Firefox with stealth settings."""
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.firefox.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = await browser.new_context(
        user_agent=_UA,
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
        java_script_enabled=True,
        timezone_id="America/Denver",
        geolocation={"latitude": 40.5725, "longitude": -111.8590},  # Sandy UT
        permissions=["geolocation"],
    )
    await context.add_init_script(_STEALTH_JS)
    # Add cookies to look like a returning visitor
    await context.add_cookies([{
        "name": "visited", "value": "1", "domain": ".truepeoplesearch.com", "path": "/",
    }, {
        "name": "visited", "value": "1", "domain": ".fastpeoplesearch.com", "path": "/",
    }, {
        "name": "visited", "value": "1", "domain": ".thatsthem.com", "path": "/",
    }])
    return pw, browser, context


async def _human_interact(page):
    """Simulate human behavior to bypass bot detection."""
    # Random mouse movements
    for _ in range(random.randint(2, 4)):
        x = random.randint(100, 1200)
        y = random.randint(100, 600)
        await page.mouse.move(x, y, steps=random.randint(5, 15))
        await asyncio.sleep(random.uniform(0.1, 0.3))
    # Scroll down slightly
    await page.evaluate("window.scrollBy(0, " + str(random.randint(100, 300)) + ")")
    await asyncio.sleep(random.uniform(0.5, 1.5))
    # Scroll back up
    await page.evaluate("window.scrollBy(0, -" + str(random.randint(50, 150)) + ")")
    await asyncio.sleep(random.uniform(0.3, 0.8))


async def _safe_text(page, selector: str, default: str = "") -> str:
    """Extract text from a selector, return default if not found."""
    try:
        el = await page.query_selector(selector)
        if el:
            return (await el.inner_text()).strip()
    except:
        pass
    return default


async def _safe_texts(page, selector: str) -> list[str]:
    """Extract text from all matching elements."""
    try:
        els = await page.query_selector_all(selector)
        return [((await el.inner_text()).strip()) for el in els if el]
    except:
        return []


# ── TruePeopleSearch ──────────────────────────────────────────────────────
async def scrape_truepeoplesearch(name: str, city: str = "", state: str = "") -> dict:
    """Scrape TruePeopleSearch for person records."""
    t0 = time.time()
    parts = name.strip().split()
    if len(parts) < 2:
        return {"error": "Need first and last name", "source": "truepeoplesearch"}

    # Build search URL
    name_slug = "-".join(p.lower() for p in parts)
    loc_slug = ""
    if city and state:
        loc_slug = f"/{city.lower().replace(' ', '-')}-{state.upper()}"
    url = f"https://www.truepeoplesearch.com/results?name={'+'.join(parts)}"
    if city:
        url += f"&citystatezip={city}+{state}"

    pw, browser, context = await _get_browser()
    try:
        page = await context.new_page()
        # First visit homepage to establish session
        await page.goto("https://www.truepeoplesearch.com", wait_until="domcontentloaded", timeout=15000)
        await _human_interact(page)
        await asyncio.sleep(random.uniform(1.5, 3.0))
        # Now navigate to search results
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await _human_interact(page)
        await asyncio.sleep(random.uniform(2, 4))

        content = await page.content()

        # Check for captcha/block — try to wait it out
        if "captcha" in content.lower() or "challenge" in content.lower():
            await asyncio.sleep(5)  # Wait for JS challenge to resolve
            await _human_interact(page)
            await asyncio.sleep(3)
            content = await page.content()
            if "captcha" in content.lower():
                # Last resort: take screenshot for debugging
                return {"error": "Captcha detected after human simulation", "source": "truepeoplesearch",
                        "url": url, "elapsed": round(time.time() - t0, 1)}

        # Extract results
        results = []
        cards = await page.query_selector_all("div.card-summary")
        if not cards:
            # Alternative selector patterns
            cards = await page.query_selector_all("[data-detail-link]")

        for card in cards[:5]:  # Top 5 results
            record = {}
            # Name
            name_el = await card.query_selector("a.h4, .person-name, h2 a")
            if name_el:
                record["name"] = (await name_el.inner_text()).strip()

            # Age/Location
            detail = await card.query_selector(".person-detail, .detail-box-content")
            if detail:
                text = (await detail.inner_text()).strip()
                # Extract age
                age_match = re.search(r'Age\s*(\d+)', text)
                if age_match:
                    record["age"] = age_match.group(1)
                # Extract location
                record["detail"] = text[:200]

            # Address
            addr_el = await card.query_selector(".address, .person-address")
            if addr_el:
                record["address"] = (await addr_el.inner_text()).strip()

            # Phone
            phone_els = await card.query_selector_all(".phone, .person-phone")
            if phone_els:
                record["phones"] = [(await p.inner_text()).strip() for p in phone_els[:3]]

            if record.get("name"):
                results.append(record)

        # If no structured results, try getting raw text
        if not results:
            body = await _safe_text(page, "body")
            # Extract any useful patterns
            phones = re.findall(r'\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}', body)
            ages = re.findall(r'Age\s*(\d+)', body)
            addrs = re.findall(r'\d+\s+\w+[\w\s]+(?:St|Ave|Rd|Dr|Ln|Blvd|Way|Ct|Pl)[\w\s,]+\d{5}', body)
            if phones or ages or addrs:
                results.append({
                    "raw_phones": phones[:5],
                    "raw_ages": ages[:3],
                    "raw_addresses": addrs[:3],
                })

        await page.close()
        return {
            "source": "truepeoplesearch",
            "url": url,
            "results": results,
            "count": len(results),
            "elapsed": round(time.time() - t0, 1),
        }

    except Exception as e:
        return {"error": str(e), "source": "truepeoplesearch", "elapsed": round(time.time() - t0, 1)}
    finally:
        await context.close()
        await browser.close()
        await pw.stop()


# ── FastPeopleSearch ──────────────────────────────────────────────────────
async def scrape_fastpeoplesearch(name: str, city: str = "", state: str = "") -> dict:
    """Scrape FastPeopleSearch for person records."""
    t0 = time.time()
    parts = name.strip().split()
    if len(parts) < 2:
        return {"error": "Need first and last name", "source": "fastpeoplesearch"}

    name_slug = "-".join(p.lower() for p in parts)
    url = f"https://www.fastpeoplesearch.com/name/{name_slug}"
    if city and state:
        url += f"_{city.lower().replace(' ', '-')}-{state.lower()}"

    pw, browser, context = await _get_browser()
    try:
        page = await context.new_page()
        await page.goto("https://www.fastpeoplesearch.com", wait_until="domcontentloaded", timeout=15000)
        await _human_interact(page)
        await asyncio.sleep(random.uniform(1.5, 3.0))
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await _human_interact(page)
        await asyncio.sleep(random.uniform(2, 4))

        content = await page.content()
        if "captcha" in content.lower() or "challenge" in content.lower() or "cloudflare" in content.lower():
            await asyncio.sleep(5)
            await _human_interact(page)
            await asyncio.sleep(3)
            content = await page.content()
            if "captcha" in content.lower() or "challenge" in content.lower():
                return {"error": "Captcha/Cloudflare detected after human sim", "source": "fastpeoplesearch",
                        "url": url, "elapsed": round(time.time() - t0, 1)}

        results = []
        # FastPeopleSearch uses detail-box-address, detail-box-phone patterns
        cards = await page.query_selector_all("div.people-list-section, div.card")

        for card in cards[:5]:
            record = {}
            name_el = await card.query_selector("h2 a, .people-name a, a[href*='/name/']")
            if name_el:
                record["name"] = (await name_el.inner_text()).strip()

            # Age and location from the card text
            card_text = (await card.inner_text()).strip()
            age_match = re.search(r'(?:Age|age)\s*(\d+)', card_text)
            if age_match:
                record["age"] = age_match.group(1)

            # Address
            addr_els = await card.query_selector_all(".detail-box-address, .address")
            if addr_els:
                record["addresses"] = [(await a.inner_text()).strip() for a in addr_els[:3]]

            # Phone
            phone_els = await card.query_selector_all(".detail-box-phone a, .phone a")
            if phone_els:
                record["phones"] = [(await p.inner_text()).strip() for p in phone_els[:3]]

            # Relatives
            rel_els = await card.query_selector_all(".detail-box-associates a, .relative a")
            if rel_els:
                record["relatives"] = [(await r.inner_text()).strip() for r in rel_els[:5]]

            if record.get("name"):
                results.append(record)

        # Fallback: extract from full page text
        if not results:
            body = await _safe_text(page, "#content, main, body")
            phones = re.findall(r'\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}', body)
            if phones:
                results.append({"raw_phones": phones[:5], "raw_text": body[:500]})

        await page.close()
        return {
            "source": "fastpeoplesearch",
            "url": url,
            "results": results,
            "count": len(results),
            "elapsed": round(time.time() - t0, 1),
        }

    except Exception as e:
        return {"error": str(e), "source": "fastpeoplesearch", "elapsed": round(time.time() - t0, 1)}
    finally:
        await context.close()
        await browser.close()
        await pw.stop()


# ── ThatsThem ─────────────────────────────────────────────────────────────
async def scrape_thatsthem(name: str = "", email: str = "", phone: str = "", ip: str = "") -> dict:
    """Scrape ThatsThem — supports name, email, phone, and IP lookups."""
    t0 = time.time()

    if email:
        url = f"https://thatsthem.com/email/{email}"
    elif phone:
        clean = re.sub(r'[^\d]', '', phone)
        url = f"https://thatsthem.com/phone/{clean}"
    elif ip:
        url = f"https://thatsthem.com/ip/{ip}"
    elif name:
        slug = "-".join(name.strip().split())
        url = f"https://thatsthem.com/name/{slug}"
    else:
        return {"error": "No search target provided", "source": "thatsthem"}

    pw, browser, context = await _get_browser()
    try:
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await _human_interact(page)
        await asyncio.sleep(random.uniform(2, 4))

        content = await page.content()
        if "captcha" in content.lower() or "challenge" in content.lower():
            await asyncio.sleep(5)
            await _human_interact(page)
            await asyncio.sleep(3)
            content = await page.content()
            if "captcha" in content.lower():
                return {"error": "Captcha detected after human sim", "source": "thatsthem", "url": url}

        # Extract result cards
        results = []
        cards = await page.query_selector_all("div.ThatsThem-people-record, div.result-card")

        for card in cards[:5]:
            record = {}
            record["name"] = await _safe_text(card, ".ThatsThem-people-name, h2")
            record["address"] = await _safe_text(card, ".ThatsThem-people-address, .address")
            record["phone"] = await _safe_text(card, ".ThatsThem-people-phone, .phone")
            record["email"] = await _safe_text(card, ".ThatsThem-people-email, .email")
            record["age"] = await _safe_text(card, ".ThatsThem-people-age, .age")
            if any(v for v in record.values()):
                results.append({k: v for k, v in record.items() if v})

        # Fallback
        if not results:
            body = await _safe_text(page, "body")
            results.append({"raw_text": body[:800]})

        await page.close()
        return {
            "source": "thatsthem",
            "url": url,
            "results": results,
            "count": len(results),
            "elapsed": round(time.time() - t0, 1),
        }

    except Exception as e:
        return {"error": str(e), "source": "thatsthem", "elapsed": round(time.time() - t0, 1)}
    finally:
        await context.close()
        await browser.close()
        await pw.stop()


# ── County Property Assessor ──────────────────────────────────────────────
async def scrape_county_assessor(address: str, county: str = "salt-lake", state: str = "UT") -> dict:
    """Scrape county assessor for property records."""
    t0 = time.time()

    # Salt Lake County (Utah) assessor
    if state.upper() == "UT" and "salt" in county.lower():
        url = f"https://slco.org/assessor/new/valuationInfoResult.cfm?parcel_id=&saddress={address.replace(' ', '+')}"
    else:
        # Generic — try county assessor via Google
        url = f"https://www.google.com/search?q={county}+county+{state}+assessor+{address.replace(' ', '+')}"

    pw, browser, context = await _get_browser()
    try:
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(random.uniform(2, 4))

        body = await _safe_text(page, "body")

        # Extract property data patterns
        record = {"source": "county_assessor", "url": url}

        # Owner name
        owner = re.search(r'(?:Owner|OWNER|owner)[:\s]+([A-Z][\w\s,]+?)(?:\n|<)', body)
        if owner: record["owner"] = owner.group(1).strip()

        # Assessed value
        value = re.search(r'(?:Assessed|Market|Appraised)[:\s]*\$?([\d,]+)', body)
        if value: record["assessed_value"] = value.group(1)

        # Tax amount
        tax = re.search(r'(?:Tax|Taxes|Annual)[:\s]*\$?([\d,.]+)', body)
        if tax: record["tax_amount"] = tax.group(1)

        # Year built
        yr = re.search(r'(?:Year Built|YearBuilt|Built)[:\s]*(\d{4})', body)
        if yr: record["year_built"] = yr.group(1)

        # Sq footage
        sqft = re.search(r'(?:Sq\s*Ft|Square\s*Feet|Living\s*Area)[:\s]*([\d,]+)', body)
        if sqft: record["square_feet"] = sqft.group(1)

        # Parcel ID
        parcel = re.search(r'(?:Parcel|APN|PIN)[:\s]*([\w-]+)', body)
        if parcel: record["parcel_id"] = parcel.group(1)

        record["raw_text"] = body[:1000]
        record["elapsed"] = round(time.time() - t0, 1)

        await page.close()
        return record

    except Exception as e:
        return {"error": str(e), "source": "county_assessor", "elapsed": round(time.time() - t0, 1)}
    finally:
        await context.close()
        await browser.close()
        await pw.stop()


# ── Combined Search (parallel) ────────────────────────────────────────────
async def full_people_search(name: str, city: str = "", state: str = "",
                              email: str = "", phone: str = "", ip: str = "",
                              address: str = "") -> dict:
    """Run all people search sources in parallel, return combined results."""
    t0 = time.time()
    tasks = {}

    if name:
        tasks["truepeoplesearch"] = scrape_truepeoplesearch(name, city, state)
        tasks["fastpeoplesearch"] = scrape_fastpeoplesearch(name, city, state)

    if email or phone or ip or name:
        tasks["thatsthem"] = scrape_thatsthem(name=name, email=email, phone=phone, ip=ip)

    if address and state:
        county = "salt-lake" if state.upper() == "UT" else ""
        tasks["county_assessor"] = scrape_county_assessor(address, county, state)

    if not tasks:
        return {"error": "No search targets provided"}

    # Execute all in parallel
    keys = list(tasks.keys())
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    combined = {}
    for key, result in zip(keys, results):
        if isinstance(result, Exception):
            combined[key] = {"error": str(result)}
        else:
            combined[key] = result

    combined["_total_elapsed"] = round(time.time() - t0, 1)
    combined["_sources_queried"] = len(keys)
    return combined
