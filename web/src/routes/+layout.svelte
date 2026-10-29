<script lang="ts">
	import './layout.css';
	import { onMount } from 'svelte';
	import { configStore } from '$lib/stores/config.svelte';
	import { installClientErrorReporting } from '$lib/client-errors';
	import favicon from '$lib/assets/favicon.svg';
	import { theme } from '$lib/stores/theme.svelte';
	import Toaster from '$lib/components/Toaster.svelte';

	theme.init();
	onMount(() => {
		let stopped = false;
		let cleanup = () => {};
		void configStore.load().then(() => {
			if (!stopped && configStore.config?.client_errors_enabled)
				cleanup = installClientErrorReporting();
		});
		return () => {
			stopped = true;
			cleanup();
		};
	});

	let { children } = $props();
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>

{@render children()}
<Toaster />
