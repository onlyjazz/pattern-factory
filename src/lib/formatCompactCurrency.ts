/**
 * Shared compact currency formatter for the UI.
 *
 * Mirrors `_format_compact_currency` in backend/services/close_service.py, which
 * renders the SLE value handed to Close. Keep the two in step: they are one
 * presentation rule applied on either side of the wire.
 *
 *   under $1,000      -> plain dollars, e.g. "$410"
 *   under $1,000,000  -> thousands,     e.g. "$410K"
 *   $1,000,000 and up -> millions,      e.g. "$4.1M", "$5,037.4M"
 *
 * One decimal is kept and a trailing .0 dropped, so 410000 renders "$410K" and
 * 4100000 renders "$4.1M". Amounts below $1,000 stay plain rather than becoming
 * "$0.4K", and null/undefined/NaN render as '-' so a product with no model (or
 * no matching threats) is distinguishable from one with zero exposure.
 */
export function formatCompactCurrency(value: number | null | undefined): string {
	if (value === null || value === undefined || Number.isNaN(value)) return '-';

	const sign = value < 0 ? '-' : '';
	const amount = Math.abs(value);

	if (amount < 1000) {
		return `${sign}$${amount.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
	}

	const thousands = amount / 1000;
	const scaled = thousands < 1000 ? thousands : thousands / 1000;
	const suffix = thousands < 1000 ? 'K' : 'M';

	let text = scaled.toLocaleString('en-US', {
		minimumFractionDigits: 1,
		maximumFractionDigits: 1
	});
	if (text.endsWith('.0')) text = text.slice(0, -2);

	return `${sign}$${text}${suffix}`;
}
