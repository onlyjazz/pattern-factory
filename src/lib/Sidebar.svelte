<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';

	let currentPath = '';
	let views: any[] = [];
	let viewsLoading = false;
	let viewsError = '';
	const apiBase = 'http://localhost:8000';

	const links = [
		{ name: "Patterns", href: "/patterns" }
	];

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
				<i class="material-icons">list</i>
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
						title={view.summary}
					>
						<i class="material-icons">table_chart</i>
						{view.summary || view.table_name}
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
		padding: 1rem 1.5rem;
		display: flex;
		align-items: center;
		gap: 0.75rem;
		color: rgba(255,255,255,0.6);
		text-decoration: none;
		transition: all 0.2s ease;
	}
	.main-nav__item:hover {
		color: rgba(255,255,255,0.8);
		background: rgba(255,255,255,0.08);
	}
	.main-nav__item_active {
		color: #fff;
		background: rgba(255,255,255,0.12);
	}
	.main-nav__item i {
		font-size: 20px;
	}
	.views-section {
		margin-top: 1rem;
		border-top: 1px solid rgba(255,255,255,0.1);
		padding-top: 1rem;
	}
	.views-title {
		padding: 0.75rem 1.5rem;
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		color: rgba(255,255,255,0.5);
		letter-spacing: 0.05em;
	}
	.main-nav__view {
		padding: 0.75rem 1.5rem;
		font-size: 0.875rem;
	}
	.views-loading,
	.views-error {
		padding: 1rem 1.5rem;
		font-size: 0.875rem;
		color: rgba(255,255,255,0.5);
	}
	.views-error {
		color: #ff6b6b;
	}
</style>
