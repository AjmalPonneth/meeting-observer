(() => {
	if (window.__meetAudioCaptureInstalled) {
		console.log("[MeetAudio] already installed");
		return;
	}

	window.__meetAudioCaptureInstalled = true;
	window.__meetAudioInjected = true;

	const logPrefix = "[MeetAudio]";
	const callbackName = "onMeetMixedAudioChunk";
	const stopFunctionName = "__meetAudioStop";

	console.log(`${logPrefix} SCRIPT EXECUTED`, location.href);

	const OriginalRTCPeerConnection =
		window.RTCPeerConnection || window.webkitRTCPeerConnection;

	if (!OriginalRTCPeerConnection) {
		console.error(`${logPrefix} RTCPeerConnection not available`);
		return;
	}

	if (typeof MediaStreamTrackProcessor === "undefined") {
		console.error(`${logPrefix} MediaStreamTrackProcessor not available`);
		return;
	}

	const AudioContextClass = window.AudioContext || window.webkitAudioContext;

	if (!AudioContextClass) {
		console.error(`${logPrefix} AudioContext not available`);
		return;
	}

	const audioCtx = new AudioContextClass();
	const mixerDestination = audioCtx.createMediaStreamDestination();

	const peerConnections = [];
	const connectedTracks = new Set();
	const mixedAudioSources = new Map();

	let reader = null;
	let abortController = null;
	let chunksSent = 0;
	let scanInterval = null;

	async function startProcessor() {
		if (reader) return;

		const mixedTrack = mixerDestination.stream.getAudioTracks()[0];

		if (!mixedTrack) {
			console.error(`${logPrefix} No mixed audio track`);
			return;
		}

		const processor = new MediaStreamTrackProcessor({ track: mixedTrack });
		reader = processor.readable.getReader();
		abortController = new AbortController();

		console.log(`${logPrefix} Processor started`);

		try {
			while (!abortController.signal.aborted) {
				const { done, value: frame } = await reader.read();

				if (done || !frame) {
					break;
				}

				try {
					const samples = frame.numberOfFrames;
					const channels = frame.numberOfChannels;
					const output = new Float32Array(samples);

					if (channels > 1) {
						const channelData = new Float32Array(samples);

						for (let ch = 0; ch < channels; ch++) {
							frame.copyTo(channelData, { planeIndex: ch });

							for (let i = 0; i < samples; i++) {
								output[i] += channelData[i];
							}
						}

						for (let i = 0; i < samples; i++) {
							output[i] /= channels;
						}
					} else {
						frame.copyTo(output, { planeIndex: 0 });
					}

					if (typeof window[callbackName] === "function") {
						window[callbackName]({
							audioData: Array.from(output),
							sampleRate: frame.sampleRate,
							timestamp: frame.timestamp,
							numberOfFrames: samples,
						});

						chunksSent++;

						if (chunksSent === 1) {
							console.log(`${logPrefix} First audio chunk sent`);
						} else if (chunksSent % 100 === 0) {
							console.log(`${logPrefix} chunks=${chunksSent}`);
						}
					} else {
						console.error(`${logPrefix} callback missing: ${callbackName}`);
					}
				} catch (err) {
					console.error(`${logPrefix} frame processing failed`, err);
				} finally {
					try {
						frame.close();
					} catch (_) { }
				}
			}
		} catch (err) {
			if (abortController?.signal?.aborted) {
				console.log(`${logPrefix} processor aborted`);
			} else {
				console.error(`${logPrefix} processor error`, err);
			}
		} finally {
			try {
				reader?.releaseLock();
			} catch (_) { }

			reader = null;
			console.log(`${logPrefix} Processor stopped chunks=${chunksSent}`);
		}
	}

	function connectTrack(track) {
		if (!track || track.kind !== "audio") return;
		if (connectedTracks.has(track.id)) return;

		connectedTracks.add(track.id);

		try {
			if (audioCtx.state === "suspended") {
				audioCtx.resume().catch(() => { });
			}

			const stream = new MediaStream([track]);
			const source = audioCtx.createMediaStreamSource(stream);

			source.connect(mixerDestination);
			mixedAudioSources.set(track.id, source);

			console.log(`${logPrefix} Audio track connected`, track.id);

			startProcessor();

			track.addEventListener("ended", () => {
				try {
					source.disconnect();
				} catch (_) { }

				mixedAudioSources.delete(track.id);
				connectedTracks.delete(track.id);

				console.log(`${logPrefix} Audio track ended`, track.id);
			});
		} catch (err) {
			console.error(`${logPrefix} connectTrack failed`, err);
		}
	}

	function scanPC(pc) {
		try {
			for (const receiver of pc.getReceivers()) {
				const track = receiver.track;

				if (track && track.kind === "audio") {
					console.log(`${logPrefix} Receiver audio track found`, track.id);
					connectTrack(track);
				}
			}
		} catch (err) {
			console.error(`${logPrefix} scanPC failed`, err);
		}
	}

	function PatchedRTCPeerConnection(...args) {
		const pc = new OriginalRTCPeerConnection(...args);
		peerConnections.push(pc);

		console.log(`${logPrefix} RTCPeerConnection created`);

		pc.addEventListener("track", (event) => {
			if (event.track && event.track.kind === "audio") {
				console.log(`${logPrefix} track event audio`, event.track.id);
				connectTrack(event.track);
			}
		});

		setTimeout(() => scanPC(pc), 500);
		setTimeout(() => scanPC(pc), 1500);
		setTimeout(() => scanPC(pc), 3000);
		setTimeout(() => scanPC(pc), 7000);

		return pc;
	}

	PatchedRTCPeerConnection.prototype = OriginalRTCPeerConnection.prototype;
	Object.setPrototypeOf(PatchedRTCPeerConnection, OriginalRTCPeerConnection);

	window.RTCPeerConnection = PatchedRTCPeerConnection;
	window.webkitRTCPeerConnection = PatchedRTCPeerConnection;

	scanInterval = setInterval(() => {
		peerConnections.forEach(scanPC);
	}, 5000);

	window[stopFunctionName] = async () => {
		console.log(`${logPrefix} stopping`);

		if (scanInterval) {
			clearInterval(scanInterval);
			scanInterval = null;
		}

		if (abortController) {
			abortController.abort();
		}

		if (reader) {
			try {
				await reader.cancel();
			} catch (_) { }
		}

		for (const source of mixedAudioSources.values()) {
			try {
				source.disconnect();
			} catch (_) { }
		}

		mixedAudioSources.clear();
		connectedTracks.clear();

		console.log(`${logPrefix} stopped`);
	};

	window.addEventListener("beforeunload", () => {
		if (typeof window[stopFunctionName] === "function") {
			window[stopFunctionName]();
		}
	});

	console.log(`${logPrefix} RTCPeerConnection patched`);
})();

