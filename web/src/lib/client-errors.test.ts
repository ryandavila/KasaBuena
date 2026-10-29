import { afterEach, expect, it, vi } from 'vitest';
import { installClientErrorReporting, reportClientError } from './client-errors';

afterEach(() => vi.restoreAllMocks());
it('is opt-in and stops reporting after cleanup', () => {
	const fetch = vi
		.spyOn(globalThis, 'fetch')
		.mockResolvedValue(new Response(null, { status: 204 }));
	reportClientError('error', 'before');
	expect(fetch).not.toHaveBeenCalled();
	const cleanup = installClientErrorReporting();
	window.dispatchEvent(new ErrorEvent('error', { message: 'uncaught' }));
	expect(fetch).toHaveBeenCalledTimes(1);
	expect(JSON.parse(fetch.mock.calls[0][1]?.body as string)).toMatchObject({
		kind: 'error',
		message: 'uncaught'
	});
	cleanup();
	window.dispatchEvent(new ErrorEvent('error', { message: 'after' }));
	expect(fetch).toHaveBeenCalledTimes(1);
});
it('bounds reports and never recurses on a failed reporting request', async () => {
	const fetch = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('offline'));
	const cleanup = installClientErrorReporting();
	for (let i = 0; i < 40; i++) reportClientError('network', 'offline');
	await Promise.resolve();
	expect(fetch.mock.calls.length).toBeLessThanOrEqual(20);
	cleanup();
});
