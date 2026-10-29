<script lang="ts">
	import { onMount } from 'svelte';
	import { getDiagnostics, errorMessage } from '$lib/api/client';
	import type { Diagnostics } from '$lib/api/types';
	import { toasts } from '$lib/stores/toasts.svelte';
	let report = $state<Diagnostics | null>(null);
	let loading = $state(false);
	let error = $state('');
	async function refresh() {
		loading = true;
		error = '';
		try {
			report = await getDiagnostics();
		} catch (e) {
			error = errorMessage(e, 'Could not load diagnostics');
		} finally {
			loading = false;
		}
	}
	async function copy() {
		if (!report) return;
		try {
			await navigator.clipboard.writeText(JSON.stringify(report, null, 2));
			toasts.push('Diagnostics copied', 'info');
		} catch {
			toasts.push('Clipboard unavailable. Select and copy the report below.', 'error');
		}
	}
	function date(value: string | null) {
		return value ? new Date(value).toLocaleString() : 'Never';
	}
	onMount(refresh);
</script>

<section class="px-5 py-4">
	<h3 class="font-display text-sm font-semibold text-ink">Diagnostics</h3>
	<p class="mt-1 text-xs text-muted">
		Current health and recent activity. History resets when the server restarts.
	</p>
	<div class="my-3 flex gap-3">
		<button
			class="rounded-xl border border-line px-3 py-2 text-sm text-ink"
			onclick={refresh}
			disabled={loading}>{loading ? 'Loading…' : 'Refresh'}</button
		>
		<button
			class="rounded-xl border border-line px-3 py-2 text-sm text-ink"
			onclick={copy}
			disabled={!report}>Copy report</button
		>
	</div>
	{#if error}<p class="text-sm text-muted" role="alert">{error}</p>{/if}
	{#if report}
		<p class="text-sm text-ink">
			{report.ready ? 'Ready' : 'Not ready'}{report.discovering ? ' — discovering devices' : ''}
		</p>
		<p class="mt-1 text-xs text-muted">
			KasaBuena {report.app_version} · python-kasa {report.python_kasa_version}
		</p>
		<p class="mt-1 text-xs text-muted">
			Cloud fallback {report.cloud_fallback_enabled ? 'enabled' : 'disabled'} · {report.cloud_device_count}
			cloud devices
		</p>
		{#each report.warnings as warning, i (i)}<p class="mt-2 text-sm text-muted">{warning}</p>{/each}
		<p class="mt-3 text-xs text-muted">Last scan: {date(report.last_scan_at)}</p>
		{#if report.last_scan}
			<p class="text-xs text-muted">
				{report.last_scan.devices.length} found · {report.last_scan.skipped.length} skipped · {report.last_scan.stats.duration_seconds.toFixed(
					2
				)} seconds
			</p>
		{/if}
		<details class="mt-3 text-sm text-muted">
			<summary class="cursor-pointer">Device health ({report.devices.length})</summary>
			<div class="overflow-x-auto">
				<table class="mt-2 w-full text-left text-xs">
					<thead><tr><th>Host</th><th>Last seen</th><th>Failures</th><th>Last error</th></tr></thead
					>
					<tbody
						>{#each report.devices as device (device.host)}<tr
								><td class="p-2 font-mono">{device.host}</td><td class="p-2"
									>{date(device.last_seen)}</td
								><td class="p-2">{device.consecutive_failures}</td><td class="p-2"
									>{device.last_error ?? 'None'}{device.error_class
										? ` (${device.error_class})`
										: ''}</td
								></tr
							>{/each}</tbody
					>
				</table>
			</div>
		</details>
		<details class="mt-3 text-sm text-muted">
			<summary class="cursor-pointer"
				>Recent jobs and deliveries ({report.recent_runs.length})</summary
			>
			<div class="overflow-x-auto">
				<table class="mt-2 w-full text-left text-xs">
					<thead><tr><th>When</th><th>Job / trigger</th><th>Result</th></tr></thead>
					<tbody
						>{#each report.recent_runs as run, i (i)}<tr>
								<td class="p-2">{date(run.started_at)}</td>
								<td class="p-2">{run.job} / {run.trigger}<br />{run.target ?? ''}</td>
								<td class="p-2"
									>{run.result}{run.status_code ? ` (HTTP ${run.status_code})` : ''} · {run.duration_seconds.toFixed(
										2
									)}s<br />{run.error ?? ''}</td
								>
							</tr>{/each}</tbody
					>
				</table>
			</div>
		</details>

		<details class="mt-3 text-sm text-muted">
			<summary class="cursor-pointer">Full report</summary>
			<textarea
				aria-label="Diagnostics JSON"
				readonly
				rows="12"
				class="mt-2 w-full rounded-lg bg-raised p-3 font-mono text-xs"
				value={JSON.stringify(report, null, 2)}></textarea>
		</details>
	{/if}
</section>
