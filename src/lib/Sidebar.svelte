<script lang="ts">
	import { page } from '$app/stores';

	const links = [
		{ name: "Patterns", href: "/" }
	];
</script>

<aside class="page-aside">
	<nav class="main-nav">
		{#each links as link}
			<a 
				class="main-nav__item { $page.url.pathname === link.href ? 'main-nav__item_active' : '' }" 
				href={link.href}
			>
				<i class="material-icons">list</i>
				{link.name}
			</a>
		{/each}
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
	}
	.main-nav__item {
		padding: 1rem 1.5rem;
		display: block;
		color: rgba(255,255,255,0.6);
	}
	.main-nav__item_active {
		color: #fff;
		background: rgba(255,255,255,0.12);
	}
</style>