from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

URL = "https://www.landwatch.com/virginia-land-for-sale/king-george"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
            print("Title:", page.title())
            html = page.content()
            print("HTML length:", len(html))
            print(html[:3000])
        except PlaywrightTimeoutError:
            print("Timed out while loading page")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
