async () => {
	const existing = document.querySelector("[aria-label='Participants']");
	if (existing) {
		console.log("[Meet-Browser] People panel already open");
		return true;
	}

	const selectors = [
		"[aria-label='Show everyone']",
		"[aria-label='People']",
		"[data-tooltip='Show everyone']",
		"[data-tooltip='People']",
		"button[aria-label*='people' i]",
		"button[aria-label*='participants' i]",
		"button[title*='people' i]",
		"button[title*='participants' i]",
		"div[role='button'][aria-haspopup='dialog']"
	];

	for (const selector of selectors) {
		const elements = Array.from(document.querySelectorAll(selector));

		for (const element of elements) {
			if (!(element instanceof HTMLElement)) continue;
			if (element.offsetParent === null) continue;

			if (selector.includes("aria-haspopup")) {
				const text = element.textContent || "";
				const label = element.getAttribute("aria-label") || "";

				if (!/people|participant|everyone/i.test(`${text} ${label}`)) {
					continue;
				}
			}

			console.log(`[Meet-Browser] Opening people panel using ${selector}`);

			element.click();

			await new Promise((resolve) => setTimeout(resolve, 1000));

			return document.querySelector("[aria-label='Participants']") !== null;
		}
	}

	console.warn("[Meet-Browser] Could not find people button");

	return false;
}
