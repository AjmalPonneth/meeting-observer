import asyncio
import contextlib
import logging
import time
from collections.abc import Iterable

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from worker.provider.base import BaseProvider

logger = logging.getLogger(__name__)


ENTRY_MESSAGE_TIMEOUT_MS = 2_000
GRACE_PERIOD_MS = 1_000
BODY_TEXT_TIMEOUT_SECONDS = 3.0


class MeetProvider(BaseProvider):
    async def open_page(
        self,
        page: Page,
        meeting_url: str,
        streaming_input: str | None = None,
        attempts: int = 0,
        max_attempts: int = 3,
    ) -> Page:
        try:
            browser_context = page.context

            await browser_context.grant_permissions(
                permissions=["camera", "microphone"],
                origin="https://meet.google.com",
            )

            logger.info(f"Opening URL: {meeting_url}")

            await page.goto(
                meeting_url,
                wait_until="domcontentloaded",
                timeout=60_000,
            )

            page_frozen = await self._detect_page_freeze_after_goto(page)

            if page_frozen:
                logger.warning(
                    f"Page freeze detected (attempt {attempts + 1}/{max_attempts})",
                )

                if attempts < max_attempts:
                    await page.goto("about:blank")
                    await page.wait_for_timeout(1000)

                    return await self.open_page(
                        page=page,
                        meeting_url=meeting_url,
                        streaming_input=streaming_input,
                        attempts=attempts + 1,
                        max_attempts=max_attempts,
                    )

            logger.info(f"Current page URL: {page.url}")

            await self._assert_on_meet_page(page)

            return page

        except Exception as exc:
            logger.exception(f"open_page error: {exc}")
            raise

    async def join_meeting(
        self,
        page: Page,
        bot_name: str = "Meeting Bot",
        streaming_input: bool = False,
        use_camera_for_branding: bool = False,
        recording_mode: str = "speaker_view",
        cancel_check=None,
    ) -> None:
        """
        Join flow with defensive retries and transition handling.
        Raises RuntimeError if join cannot be completed.
        """

        def _default_cancel_check():
            return False

        if cancel_check is None:
            cancel_check = _default_cancel_check

        logger.info("Starting join flow...")

        await self._assert_on_meet_page(page)
        await self._dismiss_transient_dialogs(page)
        await page.wait_for_timeout(300)

        await self._click_with_inner_text(
            page=page,
            selector="span",
            texts=["Use without an account"],
            max_attempts=2,
            should_click=True,
        )

        typed = await self._type_bot_name_with_retry(page, bot_name)
        if not typed:
            logger.warning("Warning: bot name could not be confirmed")

        if streaming_input:
            await self._activate_microphone(page)
        else:
            await self._deactivate_microphone(page)

        if use_camera_for_branding:
            logger.info("Branding camera requested; keeping camera on")
        else:
            await self._deactivate_camera(page)

        if cancel_check():
            raise RuntimeError("Bot stopped before clicking join")

        initial_click = await self._click_join_cta_if_present(page)
        if initial_click:
            logger.info("Initial join CTA click succeeded")
        else:
            logger.info("Initial join CTA not found; entering retry loop")

        last_join_click_at = time.time() * 1000
        join_retry_cooldown_ms = 2000
        in_waiting_room = False
        left_waiting_room_at: float | None = None
        join_retry_count = 0

        while True:
            if cancel_check():
                raise RuntimeError("Join interrupted by external stop request")

            await self._assert_on_meet_page(page)

            if await self.detect_access_denied(page):
                raise RuntimeError("Google Meet denied entry")

            now_in_waiting_room = await self.detect_waiting_room(page)
            if now_in_waiting_room and not in_waiting_room:
                logger.info("Bot is in waiting room...")
                in_waiting_room = True

            if (
                in_waiting_room
                and not now_in_waiting_room
                and left_waiting_room_at is None
            ):
                left_waiting_room_at = time.time() * 1000

            now_ms = time.time() * 1000
            if (
                not now_in_waiting_room
                and now_ms - last_join_click_at >= join_retry_cooldown_ms
            ):
                retried = await self._click_join_cta_if_present(page)
                if retried:
                    join_retry_count += 1
                    last_join_click_at = now_ms
                    logger.info(f"Re-clicked join CTA (attempt #{join_retry_count})")

            grace_expired = (
                left_waiting_room_at is None
                or (time.time() * 1000 - left_waiting_room_at) >= GRACE_PERIOD_MS
            )

            if grace_expired:
                in_meeting = await self._is_in_meeting(page)
                if in_meeting:
                    logger.info("In-meeting state confirmed")
                    await self.prepare_recording(
                        page=page,
                        streaming_input=streaming_input,
                        use_camera_for_branding=use_camera_for_branding,
                        recording_mode=recording_mode,
                    )
                    return

            await page.wait_for_timeout(1000)

    async def detect_access_denied(self, page: Page) -> bool:
        if page is None or page.is_closed():
            return False

        try:
            await self._assert_on_meet_page(page)
        except RuntimeError:
            return True

        body_text = await self._safe_body_text(page)
        if not body_text:
            return False

        blocked_markers = [
            "You can't join this video call",
            "No one can join a meeting unless invited or admitted by the host",
            "Return to home screen",
            "You've been removed",
            "You've been removed",
            "You can't join this call",
        ]
        matched = next(
            (marker for marker in blocked_markers if marker in body_text), None
        )
        return bool(matched)

    async def detect_waiting_room(self, page: Page) -> bool:
        body_text = await self._safe_body_text(page)
        if not body_text:
            return False

        waiting_markers = [
            "Asking to be let in",
            "Someone in the call needs to let you in",
            "You'll join the call when someone lets you in",
            "Ask to join",
            "Waiting for someone to let you in",
        ]
        return any(marker in body_text for marker in waiting_markers)

    async def wait_until_joined(
        self,
        page: Page,
        timeout_ms: int = 30_000,
    ) -> bool:
        """
        Kept for compatibility. The main join state machine already waits.
        """
        deadline = time.time() + (timeout_ms / 1000)

        while time.time() < deadline:
            if await self.detect_access_denied(page):
                logger.info("Access denied while waiting to join")
                return False

            if await self._is_in_meeting(page):
                logger.info("Joined successfully")
                return True

            await page.wait_for_timeout(1000)

        logger.info("wait_until_joined timed out")
        return False

    async def prepare_recording(
        self,
        page: Page,
        streaming_input: bool = False,
        use_camera_for_branding: bool = False,
        recording_mode: str = "speaker_view",
    ) -> None:
        logger.info("Preparing recording...")

        if use_camera_for_branding:
            await self._ensure_camera_on(page)
        else:
            await self._ensure_camera_off(page)

        if streaming_input:
            await self._ensure_microphone_on(page)
        else:
            await self._ensure_microphone_off(page)

        if recording_mode != "gallery_view":
            await self._open_people_panel_with_shortcut(page)

        if recording_mode != "audio_only":
            for attempt in range(1, 4):
                changed = await self._change_layout(
                    page, attempt=attempt, max_attempts=3
                )
                if changed:
                    logger.info(f"Layout change succeeded on attempt {attempt}")
                    break
                await self._click_outside_modal(page)
                await page.wait_for_timeout(300)

    async def should_end(self, page: Page) -> bool:
        if page is None or page.is_closed():
            return True

        if await self._page_appears_frozen(page, timeout_ms=20_000):
            logger.info("Page appears frozen during meeting")
            return True

        body_text = await self._safe_body_text(page)
        if not body_text:
            return False

        end_markers = [
            "You left the meeting",
            "You've been removed from the meeting",
            "You've been removed from the meeting",
            "The call ended",
            "Return to home",
            "No one else is here",
            "No one else is in the meeting",
            "You've been removed",
            "You've been removed",
        ]
        matched = next((marker for marker in end_markers if marker in body_text), None)
        return bool(matched)

    async def leave_meeting(self, page: Page) -> None:
        for button_name in ("Leave call", "Leave"):
            try:
                await page.get_by_role("button", name=button_name).click(timeout=3000)
                return
            except Exception:
                continue

        # fallback
        with contextlib.suppress(Exception):
            await page.keyboard.press("Control+Shift+KeyH")

    async def _assert_on_meet_page(self, page: Page) -> None:
        url = page.url or ""
        if url and "meet.google.com" not in url:
            raise RuntimeError(f"Page navigated away from Google Meet: {url}")

    async def _detect_page_freeze_after_goto(self, page: Page) -> bool:
        return await self._page_appears_frozen(page, timeout_ms=10_000)

    async def _page_appears_frozen(self, page: Page, timeout_ms: int) -> bool:
        try:
            await asyncio.wait_for(
                page.evaluate("() => document.readyState"),
                timeout=timeout_ms / 1000,
            )
            return False
        except Exception:
            return True

    async def _is_in_meeting(self, page: Page) -> bool:
        if await self.detect_access_denied(page):
            return False

        selectors = [
            'button[aria-label="Leave call"]',
            'button[aria-label="Leave"]',
            'div[role="region"][aria-label="Call controls"]',
            'button[aria-label*="More options"]',
            'button[aria-label*="People"]',
            'button[aria-label*="Chat"]',
        ]
        count = await self._check_indicators(page, selectors, visible_only=True)
        if count >= 2:
            return True

        if await self.detect_waiting_room(page):
            return False

        return False

    async def _check_indicators(
        self,
        page: Page,
        selectors: Iterable[str],
        visible_only: bool = True,
    ) -> int:
        found = 0
        for selector in selectors:
            try:
                locator = page.locator(selector)
                count = await locator.count()
                if count == 0:
                    continue
                if visible_only:
                    if await locator.first.is_visible():
                        found += 1
                else:
                    found += 1
            except Exception:
                continue
        return found

    async def _safe_body_text(self, page: Page) -> str:
        try:
            async with asyncio.timeout(BODY_TEXT_TIMEOUT_SECONDS):
                return await page.locator("body").inner_text()
        except TimeoutError:
            return ""
        except Exception:
            return ""

    async def _dismiss_transient_dialogs(self, page: Page) -> bool:
        dismiss_texts = ["Dismiss", "Got it"]
        dismissed_any = False

        for text in dismiss_texts:
            try:
                button = (
                    page.locator("button, div[role=button], span[role=button]")
                    .filter(has_text=text)
                    .first
                )
                if await button.count() == 0:
                    continue

                is_visible = await button.is_visible()
                is_enabled = await button.is_enabled()
                if is_visible and is_enabled:
                    await button.click()
                    dismissed_any = True
            except Exception:
                continue

        return dismissed_any

    async def _click_with_inner_text(
        self,
        page: Page,
        selector: str,
        texts: list[str],
        max_attempts: int,
        should_click: bool = True,
    ) -> bool:
        for attempt in range(max_attempts):
            try:
                for text in texts:
                    selectors = [
                        f'{selector}:has-text("{text}")',
                        f'{selector}:text-is("{text}")',
                        f'{selector}[aria-label*="{text}"]',
                        f'button:has({selector}:has-text("{text}"))',
                    ]
                    for sel in selectors:
                        locator = page.locator(sel)
                        count = await locator.count()
                        if count > 0:
                            if should_click:
                                await locator.first.click()
                            return True
            except Exception:
                pass
            await page.wait_for_timeout(100 + attempt * 100)
        return False

    async def _type_bot_name_with_retry(self, page: Page, bot_name: str) -> bool:
        typed_name = bot_name or "Bot"

        for attempt in range(1, 11):
            ok = await self._type_bot_name(page, typed_name)
            if ok:
                logger.info(f"Bot name typed on attempt {attempt}")
                return True

            if attempt < 10:
                await self._click_outside_modal(page)
                if attempt < 5:
                    await page.wait_for_timeout(500)
                else:
                    exponential_delay = 1000 * (2 ** (attempt - 6))
                    if exponential_delay < 500:
                        exponential_delay = 500
                    logger.info(
                        f"Bot name typing failed at attempt {attempt}, "
                        "retrying in {exponential_delay}ms",
                    )
                    await page.wait_for_timeout(exponential_delay)

        return False

    async def _type_bot_name(self, page: Page, bot_name: str) -> bool:
        possible_inputs = [
            'input[aria-label="Your name"]',
            'input[type="text"]',
        ]

        for selector in possible_inputs:
            try:
                await page.wait_for_selector(selector, timeout=1000)
                await page.fill(selector, "")
                await page.fill(selector, bot_name)
                current = await page.locator(selector).input_value()
                if bot_name in current:
                    return True
            except Exception:
                continue
        return False

    async def _click_join_cta_if_present(self, page: Page) -> bool:
        join_selectors = [
            'button:has-text("Ask to join")',
            'span:has-text("Ask to join")',
            'button:has-text("Join now")',
            'span:has-text("Join now")',
            'button:has-text("Join meeting")',
            'span:has-text("Join meeting")',
            'button:has-text("Join")',
            'span:has-text("Join")',
            'button:has-text("Enter meeting")',
            'span:has-text("Enter meeting")',
            'button[aria-label*="Join"]',
            'button[aria-label*="join now"]',
            'button[aria-label*="Ask to join"]',
        ]

        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(100)

            for selector in join_selectors:
                try:
                    locator = page.locator(selector).first
                    count = await locator.count()
                    if count == 0:
                        continue

                    is_visible = await locator.is_visible()
                    is_enabled = await locator.is_enabled()
                    if is_visible and is_enabled:
                        await locator.click(timeout=2000)
                        return True
                except Exception:
                    continue
        except Exception as exc:
            logger.exception(f"[MeetProvider] Failed to click join CTA: {exc}")

        return False

    async def _click_outside_modal(self, page: Page) -> None:
        await page.wait_for_timeout(500)
        for _ in range(3):
            await page.mouse.click(10, 10)
            await page.wait_for_timeout(10)

    async def _activate_microphone(self, page: Page) -> bool:
        try:
            button = page.locator('div[aria-label="Turn on microphone"]')
            if await button.count() > 0:
                await button.click()
                return True
        except Exception as exc:
            logger.exception(f"Failed to activate microphone: {exc}")
        return False

    async def _deactivate_microphone(self, page: Page) -> bool:
        try:
            button = page.locator('div[aria-label="Turn off microphone"]')
            if await button.count() > 0:
                await button.click()
                return True
        except Exception as exc:
            logger.exception(f"Failed to deactivate microphone: {exc}")
        return False

    async def _deactivate_camera(self, page: Page) -> bool:
        try:
            button = page.locator('div[aria-label="Turn off camera"]')
            if await button.count() > 0:
                await button.click()
                return True
        except Exception as exc:
            logger.exception(f"Failed to deactivate camera: {exc}")
        return False

    async def _is_camera_off(self, page: Page) -> bool:
        btn = page.locator('button[aria-label="Turn on camera"][data-is-muted="true"]')
        return (await btn.count()) > 0

    async def _is_microphone_off(self, page: Page) -> bool:
        btn = page.locator(
            'button[aria-label="Turn on microphone"][data-is-muted="true"]'
        )
        return (await btn.count()) > 0

    async def _toggle_camera_with_shortcut(self, page: Page) -> None:
        await page.keyboard.press("Control+KeyE")

    async def _toggle_microphone_with_shortcut(self, page: Page) -> None:
        await page.keyboard.press("Control+KeyD")

    async def _ensure_camera_on(self, page: Page) -> None:
        try:
            if not await self._is_camera_off(page):
                return
            await self._toggle_camera_with_shortcut(page)
        except Exception:
            btn = page.locator('button[aria-label="Turn on camera"]')
            if await btn.count() > 0:
                await btn.click()

    async def _ensure_camera_off(self, page: Page) -> None:
        try:
            if await self._is_camera_off(page):
                return
            await self._toggle_camera_with_shortcut(page)
        except Exception:
            btn = page.locator('button[aria-label="Turn off camera"]')
            if await btn.count() > 0:
                await btn.click()

    async def _ensure_microphone_on(self, page: Page) -> None:
        try:
            if not await self._is_microphone_off(page):
                return
            await self._toggle_microphone_with_shortcut(page)
        except Exception:
            btn = page.locator('button[aria-label="Turn on microphone"]')
            if await btn.count() > 0:
                await btn.click()

    async def _ensure_microphone_off(self, page: Page) -> None:
        try:
            if await self._is_microphone_off(page):
                return
            await self._toggle_microphone_with_shortcut(page)
        except Exception:
            btn = page.locator('button[aria-label="Turn off microphone"]')
            if await btn.count() > 0:
                await btn.click()

    async def _open_people_panel_with_shortcut(self, page: Page) -> bool:
        try:
            await page.keyboard.press("Control+Alt+KeyP")
            return True
        except Exception as exc:
            logger.exception(f"People shortcut failed: {exc}")
            return False

    async def _close_adjust_view_dialog_if_open(self, page: Page) -> None:
        """
        Best-effort cleanup for dangling Google Meet layout dialogs.

        Google Meet occasionally leaves the "Adjust view" or
        "Change layout" modal open after failed interactions,
        which can block future UI actions.

        This method safely dismisses the dialog if present.
        """
        try:
            close_button = page.locator('button[aria-label="Close"]').first

            if await close_button.is_visible(timeout=500):
                await close_button.click(timeout=1000)
                return

        except Exception:
            pass

        with contextlib.suppress(Exception):
            await page.keyboard.press("Escape")

    async def _change_layout(
        self,
        page: Page,
        attempt: int = 1,
        max_attempts: int = 3,
    ) -> bool:
        try:
            if not await self._is_in_meeting(page):
                logger.warning("layout change skipped; bot is not in meeting")
                return False

            more_options_button = page.locator(
                'div[role="region"][aria-label="Call controls"] '
                'button[aria-label="More options"]'
            )

            await more_options_button.wait_for(state="visible", timeout=3000)
            await more_options_button.click(timeout=3000)

            await page.wait_for_selector('[role="menu"]', state="visible", timeout=1500)

            change_layout_item = page.locator(
                '[role="menu"] [role="menuitem"]:has-text("Change layout"), '
                '[role="menu"] [role="menuitem"]:has-text("Adjust view")'
            ).first

            await change_layout_item.wait_for(state="visible", timeout=3000)
            await change_layout_item.click(timeout=3000)

            spotlight_option = page.locator(
                'label:has-text("Spotlight"), '
                '[role="radio"]:has-text("Spotlight"), '
                'div[role="radio"]:has-text("Spotlight")'
            ).first

            await spotlight_option.wait_for(state="visible", timeout=3000)
            await spotlight_option.click(timeout=3000)

            await self._click_outside_modal(page)

            logger.info("layout changed to spotlight")
            return True

        except PlaywrightTimeoutError as exc:
            logger.warning(
                "layout change timeout attempt=%s/%s error=%s",
                attempt,
                max_attempts,
                exc,
            )

        except Exception:
            logger.exception(
                "layout change failed attempt=%s/%s",
                attempt,
                max_attempts,
            )

        await self._close_adjust_view_dialog_if_open(page)
        return False

    async def send_entry_message(self, page: Page, enter_message: str) -> bool:
        if not await self._is_in_meeting(page):
            return False

        enter_message = enter_message[:500]
        chat_textarea_selector = (
            'textarea[placeholder="Send a message"], '
            'textarea[aria-label="Send a message to everyone"]'
        )

        try:
            await page.keyboard.press("Control+Alt+KeyC")
            await page.wait_for_timeout(200)

            try:
                await page.wait_for_selector(
                    chat_textarea_selector,
                    state="visible",
                    timeout=2000,
                )
            except PlaywrightTimeoutError:
                chat_button = page.locator(
                    ", ".join(
                        [
                            'button[aria-label*="Chat"]',
                            'button[aria-label*="chat"]',
                            'button[title*="Chat"]',
                            'button[title*="chat"]',
                            'nav button[aria-label="Chat"][role="button"]',
                            'div[role="button"][aria-label*="Chat"]',
                        ]
                    )
                )
                if await chat_button.count() == 0:
                    return False
                await chat_button.first.evaluate("(el) => el.click()")
                await page.wait_for_timeout(200)
                await page.wait_for_selector(
                    chat_textarea_selector,
                    state="visible",
                    timeout=ENTRY_MESSAGE_TIMEOUT_MS,
                )

            textarea = page.locator(chat_textarea_selector)
            await textarea.fill(enter_message, timeout=ENTRY_MESSAGE_TIMEOUT_MS)

            send_button = page.locator('button:has(i:text("send"))')
            if await send_button.count() > 0:
                await send_button.click(timeout=ENTRY_MESSAGE_TIMEOUT_MS)
                await page.keyboard.press("Control+Alt+KeyC")
                await page.wait_for_timeout(100)
                await page.keyboard.press("Control+Alt+KeyP")
                return True

            return False

        except Exception:
            return False
