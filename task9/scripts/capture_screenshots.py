"""
Drive the real app with Playwright and capture the status page + Flower while tasks move
through their states.  Run with everything up (see README):

    DEMO_STEP_DELAY=0.6 ...   # set on the worker so each state lasts long enough to catch
    python scripts/capture_screenshots.py

Outputs PNGs to ./shots/
"""
import io
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

APP = "http://localhost:8000"
FLOWER = "http://localhost:5555"
OUT = Path(__file__).resolve().parent.parent / "shots"
OUT.mkdir(exist_ok=True)


def make_demo_image() -> Path:
    img = Image.linear_gradient("L").resize((2400, 1800)).convert("RGB")
    p = OUT / "demo-product.png"
    img.save(p)
    return p


def watch(browser, name, start_url, fill, done_text, flower_path="/tasks", timeout=150):
    app = browser.new_page(viewport={"width": 1200, "height": 900})
    flower = browser.new_page(viewport={"width": 1400, "height": 800})
    app.goto(start_url)
    fill(app)
    app.wait_for_selector("#live")
    seen, tick, t0 = set(), 0, time.time()
    while time.time() - t0 < timeout:
        label = app.locator('[data-bind="status"]').inner_text().strip()
        extra = app.locator('[data-bind="conn"]').inner_text().strip()
        key = (label, app.locator(".step--active, .step--retry").count(),
               app.locator(".step--done").count(), app.locator(".variant.is-ready").count())
        if key not in seen:
            seen.add(key)
            tick += 1
            app.screenshot(path=str(OUT / f"{name}-{tick:02d}-app-{label.lower()}.png"))
            flower.goto(FLOWER + flower_path)
            flower.wait_for_timeout(700)
            flower.screenshot(path=str(OUT / f"{name}-{tick:02d}-flower.png"))
            print(f"  captured {name} #{tick}: {label}")
        if "finished" in extra:
            break
        time.sleep(0.4)
    app.close(); flower.close()


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()

        def fill_report(simulate):
            def _fill(pg):
                pg.fill("#id_requester_name", "Amina Rahman")
                pg.fill("#id_email", "amina@example.com")
                pg.fill("#id_date_from", "2025-01-01")
                pg.fill("#id_date_to", "2026-11-30")
                if simulate:
                    pg.select_option("#id_simulate", simulate)
                pg.click("button[type=submit]")
            return _fill

        print("1/4 happy path: Pending -> Processing -> Done -> email sent")
        watch(b, "report-ok", f"{APP}/reports/new/", fill_report(""), "Done")
        print("2/4 SMTP failure: email retried 3x with backoff (takes ~80s)")
        watch(b, "report-smtp-retry", f"{APP}/reports/new/", fill_report("smtp_fail"), "Done", timeout=200)
        print("3/4 report task failure: Pending -> Processing -> Failed")
        watch(b, "report-failed", f"{APP}/reports/new/", fill_report("report_fail"), "Failed")

        print("4/4 image group + chord")
        img = make_demo_image()

        def fill_product(pg):
            pg.fill("#id_name", "Trailhead Daypack 22L")
            pg.fill("#id_sku", f"tr-{int(time.time())}")
            pg.fill("#id_price", "64.00")
            pg.set_input_files("#id_original", str(img))
            pg.click("button[type=submit]")
        watch(b, "product-chord", f"{APP}/products/new/", fill_product, "Processed")

        # Flower overview pages
        pg = b.new_page(viewport={"width": 1400, "height": 800})
        for path, fname in [("/", "flower-workers.png"), ("/tasks", "flower-tasks-final.png"),
                            ("/broker", "flower-broker.png")]:
            pg.goto(FLOWER + path); pg.wait_for_timeout(800)
            pg.screenshot(path=str(OUT / fname), full_page=True)
        b.close()
    print("Done ->", OUT)


if __name__ == "__main__":
    sys.exit(main())
