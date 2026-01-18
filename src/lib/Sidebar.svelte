<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { modeStore } from '$lib/modeStore';
	import { Network, FileText, Route, ListTree, AlertTriangle, Box, Bug, Shield, TableRowsSplit } from 'lucide-svelte';

	let currentPath = '';
	let views: any[] = [];
	let viewsLoading = false;
	let viewsError = '';
	const apiBase = 'http://localhost:8000';

	const exploreLinks = [
		{ name: "Patterns", href: "/patterns", icon: Network },
		{ name: "Cards", href: "/cards", icon: FileText },
		{ name: "Paths", href: "/paths", icon: Route }
	];

	const modelLinks = [
		{ name: "Models", href: "/models", icon: ListTree },
		{ name: "Threats", href: "/threats", icon: AlertTriangle },
		{ name: "Assets", href: "/assets", icon: Box },
		{ name: "Vulnerabilities", href: "/vulnerabilities", icon: Bug },
		{ name: "Countermeasures", href: "/countermeasures", icon: Shield }
	];

	$: links = $modeStore.mode === 'explore' ? exploreLinks : modelLinks;

	onMount(() => {
		const unsubscribe = page.subscribe(($page) => {
			currentPath = $page.url.pathname;
		});

		// Fetch views from views_registry
		fetchViews();

		// Listen for refresh events from ChatInterface after a rule runs
		const onRefresh = () => fetchViews();
		window.addEventListener('views:refresh', onRefresh);

		return () => {
			unsubscribe();
			window.removeEventListener('views:refresh', onRefresh);
		};
	});

	async function fetchViews() {
		try {
			viewsLoading = true;
			viewsError = '';
			const response = await fetch(`${apiBase}/query/views_registry`);
			if (!response.ok) throw new Error('Failed to fetch views');
			const data = await response.json();
			views = data;
		} catch (e) {
			viewsError = e instanceof Error ? e.message : 'Failed to load views';
			console.error('Failed to load views:', e);
		} finally {
			viewsLoading = false;
		}
	}

	function isViewActive(tableName: string): boolean {
		const viewParam = new URLSearchParams(new URL(currentPath, 'http://localhost').search).get('view');
		return viewParam === tableName;
	}
</script>

<aside class="page-aside">
	<nav class="main-nav">
		{#each links as link}
			<a 
				class="main-nav__item {currentPath === link.href ? 'main-nav__item_active' : ''}" 
				href={link.href}
			>
				<svelte:component this={link.icon} size={18} stroke-width={1.5} />
				{link.name}
			</a>
		{/each}

		{#if views.length > 0}
			<div class="views-section">
				<div class="views-title">Views</div>
				{#each views as view (view.id)}
					<a 
						class="main-nav__item main-nav__view {isViewActive(view.table_name) ? 'main-nav__item_active' : ''}" 
						href="/results?view={view.table_name}"
						title={view.name}
					>
						<TableRowsSplit size={18} stroke-width={1.5} />
						{view.name || view.table_name}
					</a>
				{/each}
			</div>
		{:else if viewsLoading}
			<div class="views-loading">Loading views...</div>
		{:else if viewsError}
			<div class="views-error">{viewsError}</div>
		{/if}
	</nav>
</aside>

<style>
	.page-aside {
		position: fixed;
		top: 0;
		left: 0;
		bottom: 0;
		width: 12rem;
		background: #263238;
		color: white;
		padding-top: 4.5rem;
		overflow-y: auto;
	}
	.main-nav__item {
		padding: 0.2rem 1rem;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: rgba(255, 255, 255, 0.8);
		text-decoration: none;
		transition: all 0.2s ease;
		font-size: 0.8em;
		font-weight: 400;
	}
	.main-nav__item:hover {
		color: rgba(255,255,255,0.95);
		background: rgba(255,255,255,0.08);
	}
	.main-nav__item_active {
		color: #fff;
		background: rgba(255,255,255,0.12);
		font-weight: 500;
	}
	.main-nav__item :global(svg) {
		width: 18px;
		height: 18px;
		color: inherit;
	}
	.views-section {
		margin-top: 0.5rem;
		border-top: 1px solid rgba(255,255,255,0.1);
		padding-top: 0.5rem;
	}
	.views-title {
		padding: 0.5rem 1rem;
		font-size: 0.7rem;
		font-weight: 600;
		text-transform: uppercase;
		color: rgba(255,255,255,0.5);
		letter-spacing: 0.05em;
	}
	.main-nav__view {
		padding: 0.3rem 1rem;
		font-size: 0.8em;
	}
	.views-loading,
	.views-error {
		padding: 0.6rem 1rem;
		font-size: 0.8rem;
		color: rgba(255,255,255,0.5);
	}
	.views-error {
		color: #ff6b6b;
	}

	.main-nav {
		animation: sidebarFadeIn 0.25s ease;
	}

	@keyframes sidebarFadeIn {
		from {
			opacity: 0;
			transform: translateX(-8px);
		}
		to {
			opacity: 1;
			transform: translateX(0);
		}
	}
</style>
