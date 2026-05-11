({
	recordingMode,
	botName,
	callbackName,
	cleanupName,
	speakerLatency,
	mutationDebounce,
	checkInterval,
	freezeTimeout
}) => {
	console.log("[Meet-Browser] Installing speaker observer");

	if (window[cleanupName]) {
		window[cleanupName]();
	}

	let currentSpeakers = new Map();
	let mutationObserver = null;
	let checkSpeakersTimeout = null;
	let periodicCheck = null;
	let iframeObserver = null;
	let lastMutationTime = Date.now();

	let lastValidSpeakers = [];
	let lastValidSpeakerCheck = Date.now();

	const FREEZE_TIMEOUT_MS = 30_000;

	function normalizeName(value) {
		if (!value) return null;

		let name = String(value)
			.replace(/\s+/g, " ")
			.replace(/\s*\(You\)\s*/gi, "")
			.replace(/\s*You\s*$/gi, "")
			.trim();

		if (!name) return null;

		name = name.replace(/devices$/i, "").trim();

		const half = Math.floor(name.length / 2);

		if (
			name.length % 2 === 0 &&
			name.slice(0, half).toLowerCase() === name.slice(half).toLowerCase()
		) {
			name = name.slice(0, half).trim();
		}

		if (!name) return null;
		if (name.length > 80) return null;

		const blockedExact = new Set([
			"People",
			"Chat",
			"Activities",
			"More options",
			"Leave call",
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
			"Your call is ending soon"
		]);

		if (blockedExact.has(name)) return null;

		if (
			/settings|effects|tools|reaction|screen|captions|activities|problem|options/i.test(
				name
			)
		) {
			return null;
		}

		return name;
	}

	function areMapsEqual(map1, map2) {
		if (map1.size !== map2.size) return false;

		for (const [key, value] of map1) {
			if (!map2.has(key) || map2.get(key) !== value) {
				return false;
			}
		}

		return true;
	}

	function getSpeakerRootToObserve() {
		return [
			document,
			{
				attributes: true,
				characterData: false,
				childList: true,
				subtree: true,
				attributeFilter: ["class", "aria-label", "style"]
			}
		];
	}

	function observeIframes(callback) {
		document.querySelectorAll("iframe").forEach((iframe) => {
			callback(iframe);
		});

		const observer = new MutationObserver((mutations) => {
			for (const mutation of mutations) {
				for (const node of mutation.addedNodes) {
					if (node.nodeName === "IFRAME") {
						callback(node);
					}

					if (node.nodeType === Node.ELEMENT_NODE) {
						node.querySelectorAll("iframe").forEach((iframe) => {
							callback(iframe);
						});
					}
				}
			}
		});

		observer.observe(document.body, {
			childList: true,
			subtree: true
		});

		return observer;
	}

	function getIframeDocument(iframe) {
		try {
			return iframe.contentDocument || iframe.contentWindow?.document || null;
		} catch (_) {
			return null;
		}
	}

	function isSpeakingElement(element) {
		const color = getComputedStyle(element).backgroundColor;

		return (
			color === "rgba(26, 115, 232, 0.9)" ||
			color === "rgb(26, 115, 232)" ||
			color === "rgb(11, 87, 208)" ||
			color === "rgb(168, 199, 250)"
		);
	}

	function detectSpeaking(item) {
		const label = item.getAttribute("aria-label") || "";
		const text = item.innerText || "";

		if (/speaking/i.test(`${label} ${text}`)) {
			return true;
		}

		const unmutedMic = item.querySelector('img[src*="mic_unmuted"]');

		if (unmutedMic) {
			return true;
		}

		const speakingIndicators = Array.from(item.querySelectorAll("*")).filter(
			isSpeakingElement
		);

		for (const indicator of speakingIndicators) {
			const backgroundElement = indicator.children?.[1];

			if (!backgroundElement) {
				return true;
			}

			const backgroundPosition = getComputedStyle(
				backgroundElement
			).backgroundPositionX;

			if (backgroundPosition !== "0px") {
				return true;
			}
		}

		return false;
	}

	function getParticipantsList() {
		return document.querySelector("[aria-label='Participants']");
	}

	function getSpeakerFromDocument(timestamp) {
		try {
			const now = Date.now();

			if (now - lastValidSpeakerCheck > FREEZE_TIMEOUT_MS) {
				return [];
			}

			const participantsList = getParticipantsList();

			if (!participantsList) {
				lastValidSpeakers = [];
				return [];
			}

			const participantItems = participantsList.querySelectorAll(
				'[role="listitem"]'
			);

			if (!participantItems || participantItems.length === 0) {
				lastValidSpeakers = [];
				return [];
			}

			const uniqueParticipants = new Map();
			const mergedGroups = new Map();

			for (const item of participantItems) {
				const rawAriaLabel = item.getAttribute("aria-label")?.trim();
				const ariaLabel = normalizeName(rawAriaLabel);

				if (!ariaLabel) continue;

				const rawIsMergedAudio = rawAriaLabel === "Merged audio";
				const isMergedAudio = rawIsMergedAudio;

				let cohortId = null;

				if (isMergedAudio) {
					const cohortElement = item.closest("[data-cohort-id]");

					if (cohortElement) {
						cohortId = cohortElement.getAttribute("data-cohort-id");
					}

					if (cohortId) {
						mergedGroups.set(cohortId, {
							isSpeaking: detectSpeaking(item),
							members: []
						});
					}
				}

				const isInMergedAudio = !!item.querySelector(
					'[aria-label="Adaptive audio group"]'
				);

				let participantCohortId = null;

				if (isInMergedAudio) {
					const cohortElement = item.closest("[data-cohort-id]");

					if (cohortElement) {
						participantCohortId = cohortElement.getAttribute("data-cohort-id");
					}

					if (participantCohortId && mergedGroups.has(participantCohortId)) {
						mergedGroups.get(participantCohortId).members.push(ariaLabel);
					}
				}

				if (isMergedAudio || !isInMergedAudio) {
					const uniqueKey =
						isMergedAudio && cohortId ? `Merged audio_${cohortId}` : ariaLabel;

					if (!uniqueParticipants.has(uniqueKey)) {
						uniqueParticipants.set(uniqueKey, {
							name: ariaLabel,
							isSpeaking: false,
							isPresenting: false,
							isInMergedAudio: isMergedAudio,
							cohortId: isMergedAudio ? cohortId : null
						});
					}

					const participant = uniqueParticipants.get(uniqueKey);

					const isPresenting = Array.from(item.querySelectorAll("div")).some(
						(div) => div.textContent?.trim() === "Presentation"
					);

					if (isPresenting) {
						participant.isPresenting = true;
					}

					participant.isSpeaking = detectSpeaking(item);

					uniqueParticipants.set(uniqueKey, participant);
				}
			}

			for (const [key, participant] of uniqueParticipants.entries()) {
				if (
					participant.name === "Merged audio" &&
					participant.cohortId &&
					mergedGroups.has(participant.cohortId)
				) {
					const members = mergedGroups.get(participant.cohortId).members;

					if (members.length > 0) {
						participant.name = members.join(", ");
						participant.isSpeaking = mergedGroups.get(
							participant.cohortId
						).isSpeaking;
						uniqueParticipants.set(key, participant);
					}
				}
			}

			const speakers = Array.from(uniqueParticipants.values())
				.map((participant) => ({
					name: participant.name,
					id: 0,
					timestamp,
					isSpeaking: participant.isSpeaking
				}))
				.filter((speaker) => {
					const name = normalizeName(speaker.name);

					if (!name) return false;

					speaker.name = name;

					return speaker.name.toLowerCase() !== String(botName).toLowerCase();
				});

			lastValidSpeakers = speakers;
			lastValidSpeakerCheck = now;

			return speakers;
		} catch (error) {
			console.warn("[Meet-Browser] getSpeakerFromDocument failed", error);
			return lastValidSpeakers;
		}
	}

	async function openPeoplePanelIfNeeded() {
		const participantsList = getParticipantsList();

		if (participantsList) return true;

		const possibleSelectors = [
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

		for (const selector of possibleSelectors) {
			const buttons = Array.from(document.querySelectorAll(selector));

			for (const button of buttons) {
				if (!(button instanceof HTMLElement)) continue;
				if (button.offsetParent === null) continue;

				if (selector.includes("aria-haspopup")) {
					const text = button.textContent || "";
					const label = button.getAttribute("aria-label") || "";

					if (!/people|participant|everyone/i.test(`${text} ${label}`)) {
						continue;
					}
				}

				console.log(`[Meet-Browser] Reopening people panel with ${selector}`);

				button.click();

				return true;
			}
		}

		return false;
	}

	async function emitSpeakersIfChanged(force = false) {
		try {
			const timestamp = Date.now() - speakerLatency;

			let speakers = getSpeakerFromDocument(timestamp).filter(
				(speaker) => speaker.name !== botName
			);

			const newSpeakers = new Map(
				speakers.map((speaker) => [speaker.name, speaker.isSpeaking])
			);

			if (force || !areMapsEqual(currentSpeakers, newSpeakers)) {
				console.log(
					`[Meet-Browser] Speakers changed: ${speakers.length}`,
					speakers
				);

				if (typeof window[callbackName] === "function") {
					await window[callbackName](speakers);
				}

				currentSpeakers.clear();

				for (const [name, isSpeaking] of newSpeakers) {
					currentSpeakers.set(name, isSpeaking);
				}
			}
		} catch (error) {
			console.error("[Meet-Browser] emitSpeakersIfChanged failed", error);
		}
	}

	async function setupMutationObserver() {
		const [root, options] = getSpeakerRootToObserve();

		if (mutationObserver) {
			mutationObserver.disconnect();
		}

		mutationObserver = new MutationObserver(() => {
			if (checkSpeakersTimeout !== null) {
				clearTimeout(checkSpeakersTimeout);
			}

			lastMutationTime = Date.now();

			checkSpeakersTimeout = setTimeout(() => {
				emitSpeakersIfChanged(false);
				checkSpeakersTimeout = null;
			}, mutationDebounce);
		});

		mutationObserver.observe(root, options);

		lastMutationTime = Date.now();

		console.log("[Meet-Browser] Mutation observer installed");
	}

	async function startObserver() {
		await openPeoplePanelIfNeeded();

		await setupMutationObserver();

		iframeObserver = observeIframes((iframe) => {
			const iframeDoc = getIframeDocument(iframe);

			if (!iframeDoc) return;

			const observer = new MutationObserver(() => {
				if (checkSpeakersTimeout !== null) {
					clearTimeout(checkSpeakersTimeout);
				}

				lastMutationTime = Date.now();

				checkSpeakersTimeout = setTimeout(() => {
					emitSpeakersIfChanged(false);
					checkSpeakersTimeout = null;
				}, mutationDebounce);
			});

			observer.observe(iframeDoc, {
				attributes: true,
				characterData: false,
				childList: true,
				subtree: true,
				attributeFilter: ["class", "aria-label", "style"]
			});
		});

		periodicCheck = setInterval(async () => {
			if (document.visibilityState === "hidden") {
				return;
			}

			await openPeoplePanelIfNeeded();

			if (Date.now() - lastMutationTime > freezeTimeout) {
				console.warn("[Meet-Browser] Observer freeze detected; resetting");
				await setupMutationObserver();
			}

			await emitSpeakersIfChanged(false);
		}, checkInterval);

		await emitSpeakersIfChanged(true);

		console.log("[Meet-Browser] Speaker observer ready");
	}

	window[cleanupName] = () => {
		console.log("[Meet-Browser] Cleaning speaker observer");

		if (mutationObserver) {
			mutationObserver.disconnect();
			mutationObserver = null;
		}

		if (checkSpeakersTimeout) {
			clearTimeout(checkSpeakersTimeout);
			checkSpeakersTimeout = null;
		}

		if (periodicCheck) {
			clearInterval(periodicCheck);
			periodicCheck = null;
		}

		if (iframeObserver) {
			iframeObserver.disconnect();
			iframeObserver = null;
		}

		currentSpeakers.clear();
	};

	startObserver().catch((error) => {
		console.warn("[Meet-Browser] Failed to start observer", error);
		setTimeout(startObserver, 5000);
	});

	return true;
}
