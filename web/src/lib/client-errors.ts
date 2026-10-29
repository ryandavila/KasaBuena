/** Opt-in, best-effort reporting. Uses raw fetch to avoid recursive error reports. */
let enabled = false;
let remaining = 20;
let windowStarted = 0;

export function reportClientError(
	kind: 'error' | 'rejection' | 'request' | 'network',
	message: string,
	requestId: string | null = null
) {
	if (!enabled) return;
	const now = Date.now();
	if (now - windowStarted >= 60_000) {
		windowStarted = now;
		remaining = 20;
	}
	if (remaining-- <= 0) return;
	void fetch('/api/client-errors', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			kind,
			message: message.slice(0, 1000) || 'Unknown client error',
			request_id: requestId
		})
	}).catch(() => {});
}

export function installClientErrorReporting() {
	enabled = true;
	const onError = (event: ErrorEvent) => reportClientError('error', event.message);
	const onRejection = (event: PromiseRejectionEvent) => {
		// API failures are reported by the client already.
		if (event.reason?.name === 'ApiError') return;
		reportClientError(
			'rejection',
			event.reason instanceof Error ? event.reason.message : 'Unhandled promise rejection'
		);
	};
	window.addEventListener('error', onError);
	window.addEventListener('unhandledrejection', onRejection);
	return () => {
		enabled = false;
		window.removeEventListener('error', onError);
		window.removeEventListener('unhandledrejection', onRejection);
	};
}
