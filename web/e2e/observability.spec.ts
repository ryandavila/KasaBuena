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
