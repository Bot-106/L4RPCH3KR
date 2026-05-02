"""
LinkedIn profile scraper.
Opens Chrome with the user's existing session. If LinkedIn redirects to the
login wall, logs in automatically using LINKEDIN_EMAIL / LINKEDIN_PASSWORD from .env.
Closes Chrome when done.

NOTE: Playwright requires ProactorEventLoop on Windows to spawn subprocesses.
FastAPI/uvicorn uses SelectorEventLoop, so we run playwright in a ThreadPoolExecutor
thread that creates its own ProactorEventLoop.
"""

import asyncio
import concurrent.futures
import logging
import os
import shutil
import tempfile
from typing import Any

log = logging.getLogger(__name__)

_CHROME_USER_DATA = os.path.join(
    os.environ.get("LOCALAPPDATA", r"C:\Users\arnna\AppData\Local"),
    "Google", "Chrome", "User Data"
)

_JS_EXTRACT = """
() => {
    const text = (sel, root) => {
        const el = (root || document).querySelector(sel);
        return el ? el.innerText.trim() : null;
    };

    const name = text('h1');

    const headline =
        text('.pv-text-details__left-panel .text-body-medium.break-words') ||
        text('.text-body-medium.break-words');

    const location =
        text('.pv-text-details__left-panel .pb2 .text-body-small') ||
        text('span.text-body-small.inline.t-black--light');

    const aboutSection = document.getElementById('about');
    let about = null;
    if (aboutSection) {
        const sec = aboutSection.closest('section');
        if (sec) {
            about = text('.inline-show-more-text--is-collapsed', sec)
                 || text('.inline-show-more-text', sec)
                 || text('span[aria-hidden="true"]', sec);
        }
    }

    const expSection = document.getElementById('experience');
    const experiences = [];
    if (expSection) {
        const sec = expSection.closest('section');
        if (sec) {
            for (const item of [...sec.querySelectorAll('li.artdeco-list__item')].slice(0, 6)) {
                const spans = [...item.querySelectorAll('span[aria-hidden="true"]')];
                const title   = spans[0]?.innerText.trim() || null;
                const company = spans[1]?.innerText.trim() || null;
                const dates   = spans[2]?.innerText.trim() || null;
                if (title) experiences.push({ title, company, dates });
            }
        }
    }

    const eduSection = document.getElementById('education');
    const education = [];
    if (eduSection) {
        const sec = eduSection.closest('section');
        if (sec) {
            for (const item of [...sec.querySelectorAll('li.artdeco-list__item')].slice(0, 4)) {
                const spans = [...item.querySelectorAll('span[aria-hidden="true"]')];
                const school = spans[0]?.innerText.trim() || null;
                const degree = spans[1]?.innerText.trim() || null;
                if (school) education.push({ school, degree });
            }
        }
    }

    const skillSection = document.getElementById('skills');
    const skills = [];
    if (skillSection) {
        const sec = skillSection.closest('section');
        if (sec) {
            for (const el of sec.querySelectorAll('span[aria-hidden="true"]')) {
                const t = el.innerText.trim();
                if (t && !skills.includes(t) && skills.length < 12) skills.push(t);
            }
        }
    }

    const photoEl = document.querySelector('.pv-top-card-profile-picture__image--show')
                 || document.querySelector('img.profile-photo-edit__preview')
                 || document.querySelector('.pv-top-card__photo img');
    const photoUrl = photoEl?.src || null;

    return { name, headline, location, about, experiences, education, skills, photoUrl };
}
"""


def _copy_profile_to_temp() -> str | None:
    """Copy Chrome's Default profile cookies to a temp dir so playwright
    can use the existing LinkedIn session without locking the live profile."""
    try:
        tmp = tempfile.mkdtemp(prefix="larpchekr_chrome_")
        src_profile = os.path.join(_CHROME_USER_DATA, "Default")
        dst_profile = os.path.join(tmp, "Default")
        os.makedirs(dst_profile, exist_ok=True)
        for fname in ("Cookies", "Login Data", "Web Data", "Preferences"):
            src = os.path.join(src_profile, fname)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(dst_profile, fname))
        local_state = os.path.join(_CHROME_USER_DATA, "Local State")
        if os.path.exists(local_state):
            shutil.copy2(local_state, os.path.join(tmp, "Local State"))
        return tmp
    except Exception as exc:
        log.warning("linkedin_scraper: could not copy profile: %s", exc)
        return None


async def _do_login(page: Any, email: str, password: str) -> bool:
    """Navigate to LinkedIn login, fill credentials, submit, wait for success."""
    try:
        log.info("linkedin_scraper: navigating to login page")
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=20_000)

        # Wait for the email field — LinkedIn dynamically assigns IDs (e.g. r3, username)
        email_sel = await _wait_for_any(page, ["#username", "#r3", 'input[name="session_key"]', 'input[type="email"]'], timeout=10_000)
        if not email_sel:
            log.warning("linkedin_scraper: could not find email input")
            return False

        await page.fill(email_sel, email)

        # Password field — try by name first (stable), then by adjacent ID
        pwd_sel = await _wait_for_any(page, ['input[name="session_password"]', "#password", "#r4", 'input[type="password"]'], timeout=5_000)
        if not pwd_sel:
            log.warning("linkedin_scraper: could not find password input")
            return False

        await page.fill(pwd_sel, password)
        await page.click('button[type="submit"]')

        # Wait until we leave the login/authwall pages
        await page.wait_for_url(
            lambda u: "/login" not in u and "authwall" not in u and "checkpoint" not in u,
            timeout=20_000,
        )
        await page.wait_for_timeout(2_000)
        log.info("linkedin_scraper: login succeeded, now at %s", page.url)
        return True
    except Exception as exc:
        log.warning("linkedin_scraper: login failed: %s", exc)
        return False


async def _wait_for_any(page: Any, selectors: list[str], timeout: int = 5_000) -> str | None:
    """Return the first selector that appears on the page within timeout ms."""
    import asyncio as _asyncio
    deadline = _asyncio.get_event_loop().time() + timeout / 1000
    while _asyncio.get_event_loop().time() < deadline:
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    return sel
            except Exception:
                pass
        await _asyncio.sleep(0.3)
    return None


async def _scrape_async(url: str, email: str, password: str) -> dict[str, Any]:
    from playwright.async_api import async_playwright

    dirs_to_try: list[tuple[str, bool]] = [(_CHROME_USER_DATA, False)]
    tmp = _copy_profile_to_temp()
    if tmp:
        dirs_to_try.append((tmp, True))

    for user_data_dir, is_tmp in dirs_to_try:
        try:
            async with async_playwright() as pw:
                ctx = await pw.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    channel="chrome",
                    headless=False,
                    args=[
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-component-extensions-with-background-pages",
                    ],
                )
                page = await ctx.new_page()
                try:
                    # Navigate to the profile URL and wait for it to fully settle
                    # (playwright opens about:blank first; goto waits for domcontentloaded)
                    await page.goto(url, wait_until="domcontentloaded", timeout=20_000)

                    # If we landed on about:blank or a redirect is still in progress, wait
                    if page.url in ("about:blank", "") or page.url.startswith("about:"):
                        await page.wait_for_url(lambda u: not u.startswith("about:"), timeout=10_000)

                    await page.wait_for_timeout(3_000)

                    # Hit login wall — try to log in if credentials are configured
                    if "authwall" in page.url or "/login" in page.url or "/checkpoint" in page.url:
                        if email and password:
                            logged_in = await _do_login(page, email, password)
                            if logged_in:
                                # Now navigate to the original profile URL
                                await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                                await page.wait_for_timeout(3_000)
                            else:
                                log.warning("linkedin_scraper: login failed, giving up")
                                return {}
                        else:
                            log.warning("linkedin_scraper: hit auth wall and no credentials configured")
                            return {}

                    # Final check — still on auth wall?
                    if "authwall" in page.url or "/login" in page.url:
                        log.warning("linkedin_scraper: still on auth wall after login attempt")
                        return {}

                    data: dict[str, Any] = await page.evaluate(_JS_EXTRACT)
                    data["scraped"] = True
                    data["url"] = url
                    log.info("linkedin_scraper: success — name=%s", data.get("name"))
                    return data
                finally:
                    await ctx.close()

        except Exception as exc:
            log.warning("linkedin_scraper: failed with dir=%s: %s", user_data_dir, exc)
        finally:
            if is_tmp and os.path.exists(user_data_dir):
                shutil.rmtree(user_data_dir, ignore_errors=True)

    return {}


def _scrape_sync(url: str, email: str, password: str) -> dict[str, Any]:
    """
    Runs in a ThreadPoolExecutor thread with its own ProactorEventLoop.
    Required on Windows because asyncio.create_subprocess_exec (used by playwright)
    only works with ProactorEventLoop, not SelectorEventLoop.
    """
    if hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_scrape_async(url, email, password))
    finally:
        loop.close()


async def scrape_linkedin_profile(url: str) -> dict[str, Any]:
    """Async entry point called from FastAPI. Delegates to a thread pool so
    playwright gets a ProactorEventLoop on Windows."""
    if not url or not url.startswith("http"):
        return {}

    from app.config import settings
    email = settings.linkedin_email.strip()
    password = settings.linkedin_password.strip()

    try:
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return await loop.run_in_executor(pool, _scrape_sync, url, email, password)
    except Exception as exc:
        log.warning("linkedin_scraper: executor error: %s", exc)
        return {}
