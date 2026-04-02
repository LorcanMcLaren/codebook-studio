#!/usr/bin/env python3
import os
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

APP_URL = os.environ.get("STREAMLIT_APP_URL", "https://codebook.streamlit.app/")
WAKE_BUTTON_TEXT = os.environ.get("STREAMLIT_WAKE_BUTTON_TEXT", "Yes, get this app back up")
LOAD_TIMEOUT_SECONDS = int(os.environ.get("STREAMLIT_LOAD_TIMEOUT_SECONDS", "45"))
READY_TIMEOUT_SECONDS = int(os.environ.get("STREAMLIT_READY_TIMEOUT_SECONDS", "45"))
WAKE_TIMEOUT_SECONDS = int(os.environ.get("STREAMLIT_WAKE_TIMEOUT_SECONDS", "120"))
WAKE_ATTEMPTS = int(os.environ.get("STREAMLIT_WAKE_ATTEMPTS", "2"))
ARTIFACT_DIR = Path(os.environ.get("STREAMLIT_WAKE_ARTIFACT_DIR", "artifacts"))

SLEEP_MARKERS = (
    "this app has gone to sleep due to inactivity",
    "yes, get this app back up",
)

AWAKE_SELECTORS = (
    ".stApp",
    "[data-testid='stAppViewContainer']",
    "[data-testid='stMain']",
)


def log(message: str) -> None:
    print(message, flush=True)


def xpath_literal(value: str) -> str:
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat(" + ", \"'\", ".join(f"'{part}'" for part in parts) + ")"


WAKE_BUTTON_XPATH = (
    f"//button[contains(normalize-space(), {xpath_literal(WAKE_BUTTON_TEXT)})]"
)


def build_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1600,1200")

    chrome_bin = os.environ.get("CHROME_BIN")
    if chrome_bin:
        options.binary_location = chrome_bin

    chromedriver = os.environ.get("CHROMEDRIVER")
    service = Service(executable_path=chromedriver) if chromedriver else Service()

    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(LOAD_TIMEOUT_SECONDS)
    return driver


def get_body_text(driver: webdriver.Chrome) -> str:
    elements = driver.find_elements(By.TAG_NAME, "body")
    if not elements:
        return ""
    return elements[0].text.strip().lower()


def find_visible_wake_button(driver: webdriver.Chrome):
    for button in driver.find_elements(By.XPATH, WAKE_BUTTON_XPATH):
        if button.is_displayed():
            return button
    return None


def page_has_sleep_prompt(driver: webdriver.Chrome) -> bool:
    body_text = get_body_text(driver)
    return any(marker in body_text for marker in SLEEP_MARKERS)


def page_looks_awake(driver: webdriver.Chrome) -> bool:
    for selector in AWAKE_SELECTORS:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if any(element.is_displayed() for element in elements):
            return True
    return False


def wait_for_initial_state(driver: webdriver.Chrome) -> str:
    deadline = time.time() + READY_TIMEOUT_SECONDS
    while time.time() < deadline:
        try:
            ready_state = driver.execute_script("return document.readyState")
        except WebDriverException:
            ready_state = "unknown"

        if find_visible_wake_button(driver) or page_has_sleep_prompt(driver):
            return "sleeping"

        if ready_state == "complete" and page_looks_awake(driver):
            return "awake"

        time.sleep(2)

    return "unknown"


def wait_until_awake(driver: webdriver.Chrome) -> bool:
    deadline = time.time() + WAKE_TIMEOUT_SECONDS
    while time.time() < deadline:
        button = find_visible_wake_button(driver)
        sleeping = page_has_sleep_prompt(driver)
        awake = page_looks_awake(driver)

        if awake and not sleeping:
            return True

        if button is None and not sleeping:
            return True

        time.sleep(3)

    return False


def save_debug_artifacts(driver: webdriver.Chrome, attempt: int) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    screenshot_path = ARTIFACT_DIR / f"wake-streamlit-attempt-{attempt}.png"
    html_path = ARTIFACT_DIR / f"wake-streamlit-attempt-{attempt}.html"

    try:
        driver.save_screenshot(str(screenshot_path))
        log(f"Saved screenshot to {screenshot_path}")
    except WebDriverException as error:
        log(f"Unable to save screenshot: {error}")

    try:
        html_path.write_text(driver.page_source, encoding="utf-8")
        log(f"Saved page source to {html_path}")
    except OSError as error:
        log(f"Unable to save page source: {error}")


def run_attempt(attempt: int) -> bool:
    driver = None
    try:
        log(f"[Attempt {attempt}/{WAKE_ATTEMPTS}] Opening {APP_URL}")
        driver = build_driver()

        try:
            driver.get(APP_URL)
        except TimeoutException:
            log("Initial page load timed out; inspecting the partially loaded page.")

        state = wait_for_initial_state(driver)
        log(f"Detected state: {state}")

        if state == "awake":
            log("App already appears awake.")
            return True

        if state == "sleeping":
            button = find_visible_wake_button(driver)
            if button is None:
                raise RuntimeError("Detected the sleeping page but could not find a clickable wake button.")

            log("Wake button found. Clicking it now.")
            driver.execute_script("arguments[0].click();", button)

            if wait_until_awake(driver):
                log("Wake flow completed successfully.")
                return True

            raise RuntimeError("Clicked the wake button, but the app never looked awake afterwards.")

        raise RuntimeError(
            "Could not confirm whether the app was awake or sleeping. "
            "This usually means the page did not finish rendering as expected."
        )
    except Exception as error:
        log(f"Attempt {attempt} failed: {error}")
        if driver is not None:
            save_debug_artifacts(driver, attempt)
        return False
    finally:
        if driver is not None:
            driver.quit()


def main() -> int:
    for attempt in range(1, WAKE_ATTEMPTS + 1):
        if run_attempt(attempt):
            return 0

        if attempt < WAKE_ATTEMPTS:
            log("Retrying after a short pause.")
            time.sleep(5)

    log("All wake attempts failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
