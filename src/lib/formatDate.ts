/**
 * Shared date formatter for the UI.
 *
 * AGENTS.md requires every date rendered in the interface to use the
 * abbreviated US month format, e.g. "Nov 15, 2024" — never a raw ISO string or
 * a locale-default format. Use this helper for all dates in the Product
 * workspace, including the PAT-380 Close send dates.
 */
export function formatDate(value: string | number | Date | null | undefined): string {
	if (value === null || value === undefined || value === '') return '';

	let date: Date;
	if (value instanceof Date) {
		date = value;
	} else if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
		// Date-only strings (e.g. products.date_of_final_decision) would be parsed
		// as UTC midnight, which can render as the previous day in western time
		// zones. Build a local date from the components instead.
		const [year, month, day] = value.split('-').map(Number);
		date = new Date(year, month - 1, day);
	} else {
		date = new Date(value);
	}

	if (Number.isNaN(date.getTime())) return '';

	return date.toLocaleDateString('en-US', {
		year: 'numeric',
		month: 'short',
		day: 'numeric'
	});
}
