() => {
	const participants = [];
	const seen = new Set();

	function normalizeName(value) {
		if (!value) return null;

		let name = String(value)
			.replace(/\s+/g, " ")
			.replace(/\s*\(You\)\s*/gi, "")
			.trim();

		if (!name) return null;

		// Remove duplicated text like "ponneth ajmalponneth ajmaldevices"
		name = name.replace(/devices$/i, "").trim();

		const half = Math.floor(name.length / 2);
		if (
			name.length % 2 === 0 &&
			name.slice(0, half).toLowerCase() === name.slice(half).toLowerCase()
		) {
			name = name.slice(0, half).trim();
		}

		const blocked = [
			"Audio settings",
			"Backgrounds and effects",
			"Chat with everyone",
			"Meeting tools",
			"Microphone problem. Show more info",
			"More activities in this meeting.",
			"Raise hand (ctrl + alt + h)",
			"Send a reaction",
			"Share screen",
			"This call is open to anyone",
			"Turn on captions",
			"Video settings",
			"Your call is ending soon",
			"People",
			"Activities",
			"Chat",
			"More options",
			"Leave call"
		];

		if (blocked.some((item) => name.toLowerCase() === item.toLowerCase())) {
			return null;
		}

		if (/settings|effects|tools|reaction|screen|captions|activities/i.test(name)) {
			return null;
		}

		if (name.length > 60) return null;

		return name;
	}

	function push(name, node) {
		name = normalizeName(name);

		if (!name || seen.has(name.toLowerCase())) return;

		seen.add(name.toLowerCase());

		const text = `${node.innerText || ""} ${node.getAttribute("aria-label") || ""}`;

		participants.push({
			name,
			is_speaking: /speaking/i.test(text)
		});
	}

	// Prefer actual people panel entries.
	const peoplePanel = document.querySelector(
		'[aria-label*="People" i], [aria-label*="Participants" i]'
	);

	const root = peoplePanel || document;

	const nodes = Array.from(
		root.querySelectorAll('[role="listitem"], [data-participant-id]')
	);

	for (const node of nodes) {
		const candidates = [
			node.querySelector("[data-participant-name]")?.getAttribute("data-participant-name"),
			node.querySelector("[data-participant-name]")?.textContent,
			node.getAttribute("data-participant-name"),
			node.getAttribute("aria-label"),
			node.innerText
		];

		for (const candidate of candidates) {
			const normalized = normalizeName(candidate);
			if (normalized) {
				push(normalized, node);
				break;
			}
		}
	}

	return participants;
}
