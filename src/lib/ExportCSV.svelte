<script lang="ts">
	export let data: any[] = [];
	export let fileName: string = 'export.csv';

	function formatColumnName(col: string): string {
		return col
			.split('_')
			.map(word => word.charAt(0).toUpperCase() + word.slice(1))
			.join(' ');
	}

	function convertToCSV(items: any[]): string {
		if (!items || items.length === 0) return '';

		// Get all unique keys from all objects
		const allKeys = new Set<string>();
		items.forEach(item => {
			Object.keys(item).forEach(key => allKeys.add(key));
		});

		const headers = Array.from(allKeys);

		// Create CSV content
		const csvContent = [
			// Headers - format column names from snake_case to Title Case
			headers.map(h => `"${formatColumnName(h)}"`).join(','),
			// Rows
			...items.map(item =>
				headers
					.map(header => {
						const value = item[header];
						// Escape quotes and wrap in quotes if needed
						if (value === null || value === undefined) {
							return '""';
						}
						const strValue = String(value);
						const needsQuotes =
							strValue.includes(',') || strValue.includes('"') || strValue.includes('\n');
						if (needsQuotes) {
							return `"${strValue.replace(/"/g, '""')}"`;
						}
						return `"${strValue}"`;
					})
					.join(',')
			)
		].join('\n');

		return csvContent;
	}

	function handleExport() {
		const csv = convertToCSV(data);
		const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
		const link = document.createElement('a');
		const url = URL.createObjectURL(blob);

		link.setAttribute('href', url);
		link.setAttribute('download', fileName);
		link.style.visibility = 'hidden';

		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
	}
</script>

<button class="export-button" onclick={handleExport} title="Export to CSV">
	<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
		<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
		<polyline points="7 10 12 15 17 10" />
		<line x1="12" y1="15" x2="12" y2="3" />
	</svg>
	<span>CSV</span>
</button>

<style>
	.export-button {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 8px 12px;
		background-color: #f5f5f5;
		border: 1px solid #ddd;
		border-radius: 4px;
		cursor: pointer;
		font-size: 13px;
		font-weight: 500;
		color: #333;
		transition: all 0.2s ease;
	}

	.export-button:hover {
		background-color: #efefef;
		border-color: #bbb;
		color: #000;
	}

	.export-button:active {
		background-color: #e5e5e5;
	}

	svg {
		display: block;
	}
</style>
