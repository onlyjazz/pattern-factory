<script>
	// simple header — no props, no logic
</script>

<header class="page-header">
	<div class="grid">
		<div class="grid-row">
			<div class="grid-col grid-col_12">
				<div class="logo"></div>
			</div>
			<div class="grid-col grid-col_12 tar">
				<span class="heading_4">Pattern Factory</span>
			</div>
		</div>
	</div>
</header>

<style>
	.page-header {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		height: 64px;
		background: #039be5;
		color: white;
		z-index: 10;
		display: flex;
		align-items: center;
		box-shadow: 0 2px 6px rgba(0,0,0,0.2);
	}

	.logo {
		width: 40px;
		height: 40px;
		background: url('/img/logo_white.png') center/contain no-repeat;
	}
</style>