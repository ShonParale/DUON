import asyncio, subprocess, time
from playwright.async_api import async_playwright

async def main():
    # Start fresh server (different port to avoid conflict)
    proc = subprocess.Popen(
        ['python', '-m', 'uvicorn', 'web_server:app',
         '--host', '127.0.0.1', '--port', '5001'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    time.sleep(4)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            errors = []
            page.on('console', lambda msg: errors.append('CONSOLE.' + msg.type + ': ' + msg.text))
            page.on('pageerror', lambda exc: errors.append('PAGE_ERROR: ' + str(exc)))

            await page.goto('http://127.0.0.1:5001/', wait_until='networkidle', timeout=15000)
            await asyncio.sleep(2)

            title = await page.title()
            body_len = len(await page.inner_html('body'))
            active = await page.query_selector('.page.active')
            active_id = await active.get_attribute('id') if active else 'NONE'

            print('Title:', title)
            print('Body length:', body_len)
            print('Active page:', active_id)

            for e in errors:
                print(e)
            if not errors:
                print('NO JS ERRORS')

            # Now navigate to mapping page
            nav_btn = await page.query_selector('[data-page="mapping"]')
            if nav_btn:
                await nav_btn.click()
                await asyncio.sleep(1)
                active2 = await page.query_selector('.page.active')
                active_id2 = await active2.get_attribute('id') if active2 else 'NONE'
                print('After nav to mapping, active page:', active_id2)
                canvas = await page.query_selector('#advCanvas')
                print('Canvas exists:', canvas is not None)
            else:
                print('Nav button for mapping NOT FOUND')

            for e in errors:
                print(e)

            await browser.close()
    finally:
        proc.terminate()

asyncio.run(main())
