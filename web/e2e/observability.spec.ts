import { expect, test } from '@playwright/test';

test('settings show diagnostics and a copyable report', async ({ page, request }) => {
	const ready = await request.get('/api/ready');
	expect(ready.status()).toBe(200);
	expect(ready.headers()['x-request-id']).toBeTruthy();
	await page.goto('/');
	await page.getByRole('button', { name: 'Settings', exact: true }).click();
	await expect(page.getByRole('heading', { name: 'Diagnostics' })).toBeVisible();
	await expect(page.getByRole('button', { name: 'Copy report' })).toBeEnabled();
	await page.getByText('Full report', { exact: true }).click();
	await expect(page.getByLabel('Diagnostics JSON')).toHaveValue(/python_kasa_version/);
	await expect(page.getByLabel('Diagnostics JSON')).toHaveValue(/recent_runs/);
});

test('device errors include a request ID in the toast', async ({ page }) => {
	await page.route('**/api/devices/*/power', (route) =>
		route.fulfill({
			status: 502,
			contentType: 'application/json',
			headers: { 'X-Request-ID': 'browser-test-123' },
			body: JSON.stringify({
				detail: 'Device could not be reached',
				request_id: 'browser-test-123'
			})
		})
	);
	await page.goto('/');
	await page.getByRole('switch', { name: 'Toggle Living Room Lamp' }).click();
	await expect(
		page.getByText('Device could not be reached (request browser-test-123)', { exact: true })
	).toBeVisible();
});
