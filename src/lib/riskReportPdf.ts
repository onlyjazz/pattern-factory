/**
 * Builds pdfmake document definitions for the OpenCRO risk reports
 * (Model Risk and Enterprise Risk).
 *
 * This module is intentionally free of DOM/browser APIs (the chart is
 * rasterized by the caller and passed in as a data URL) so the document
 * definitions can be reused and smoke-tested outside the browser.
 */

const BRAND_COLOR = '#FF325D';
const TITLE_COLOR = '#263238';
const LABEL_COLOR = '#666666';
const VALUE_COLOR = '#333333';
const TABLE_BORDER = '#e0e0e0';
const TAGLINE = 'The AI Chief Risk Officer for MedTech';
const DISCLAIMER =
	"This analysis was built entirely from publicly available information (FDA 510(k) filings, investor disclosures, press releases) and reflects OpenCRO's independent threat-modeling methodology — not an assessment, audit, or penetration test of the company’s actual systems, code, or infrastructure. No non-public or proprietary information was used or is claimed.";
export const SLE_LEGEND =
	'SLE = Single Loss Event. Assets at risk = sum of asset exposure × damage percentage. SLE = assets at risk × threat probability. SLE after mitigation = SLE × max(1 - target mitigation, 5%). Values are rounded to the nearest dollar.';

const TABLE_LAYOUT = {
	hLineColor: () => TABLE_BORDER,
	vLineColor: () => TABLE_BORDER,
	hLineWidth: () => 0.5,
	vLineWidth: () => 0,
	paddingLeft: () => 8,
	paddingRight: () => 8,
	paddingTop: () => 5,
	paddingBottom: () => 5
};

// -------------------------------------------------------------------------
// Formatting and SLE math
// -------------------------------------------------------------------------

export function formatCurrency(value?: number): string {
	if (value === undefined || value === null) return '-';
	return new Intl.NumberFormat('en-US', {
		style: 'currency',
		currency: 'USD',
		maximumFractionDigits: 0
	}).format(value);
}

export function formatNumber(value?: number | null): string {
	if (value === undefined || value === null) return '-';
	return value.toLocaleString('en-US');
}

export function formatPercent(value?: number): string {
	if (value === undefined || value === null) return '-';
	return `${value.toFixed(1)}%`;
}

// Percent without forced decimals (95 -> '95%', 92.5 -> '92.5%').
export function formatPercentCompact(value?: number): string {
	if (value === undefined || value === null) return '-';
	return `${Number(value.toFixed(1))}%`;
}

// SLE = assets at risk × threat probability, rounded to the nearest dollar.
export function computeSle(assetsAtRisk?: number, probabilityPct?: number): number | null {
	if (assetsAtRisk === undefined || assetsAtRisk === null) return null;
	if (probabilityPct === undefined || probabilityPct === null) return null;
	return Math.round(assetsAtRisk * (probabilityPct / 100));
}

// SLE after mitigation = SLE × max(1 - target mitigation, 5%), rounded to the nearest dollar.
export function computeSleAfterMitigation(
	sle?: number | null,
	mitigationPct?: number
): number | null {
	if (sle === undefined || sle === null) return null;
	if (mitigationPct === undefined || mitigationPct === null) return null;
	const residual = Math.max(1 - mitigationPct / 100, 0.05);
	return Math.round(sle * residual);
}

// -------------------------------------------------------------------------
// Shared report scaffolding
// -------------------------------------------------------------------------

export interface RiskThreat {
	threat_name?: string;
	product_name?: string;
	damage_description?: string;
	threat_probability?: number;
	gross_sle?: number;
	target_mitigation_pct?: number;
}

export interface RiskReportSection {
	heading: string;
	table: any;
	chartImage?: string | null;
}

export interface RiskReportOptions {
	documentTitle: string;
	facts: Array<[string, string]>;
	sections: RiskReportSection[];
	logoImage: string | null;
}

function buildTable(headers: string[], widths: any[], rows: any[][]): any {
	return {
		table: {
			headerRows: 1,
			widths,
			body: [
				headers.map((h) => ({
					text: h,
					bold: true,
					color: VALUE_COLOR,
					fillColor: '#f0f0f0',
					alignment: 'left'
				})),
				...rows
			]
		},
		layout: TABLE_LAYOUT
	};
}

function buildThreatRow(
	threat: RiskThreat,
	options: { product?: boolean; description?: boolean }
): any[] {
	const sle = computeSle(threat.gross_sle, threat.threat_probability);
	const row: any[] = [{ text: threat.threat_name || '-', color: VALUE_COLOR }];
	if (options.product) {
		row.push({ text: threat.product_name || '-', color: VALUE_COLOR });
	}
	if (options.description) {
		row.push({ text: threat.damage_description || '-', color: VALUE_COLOR });
	}
	row.push(
		{ text: formatPercentCompact(threat.threat_probability), alignment: 'center', color: VALUE_COLOR },
		{ text: formatNumber(threat.gross_sle), alignment: 'center', color: VALUE_COLOR },
		{ text: formatNumber(sle), alignment: 'center', color: VALUE_COLOR },
		{ text: formatPercentCompact(threat.target_mitigation_pct), alignment: 'center', color: VALUE_COLOR },
		{
			text: formatNumber(computeSleAfterMitigation(sle, threat.target_mitigation_pct)),
			alignment: 'center',
			color: VALUE_COLOR
		}
	);
	return row;
}

export function buildThreatTable(
	headers: string[],
	widths: any[],
	threats: RiskThreat[],
	options: { product?: boolean; description?: boolean } = {}
): any {
	return buildTable(
		headers,
		widths,
		threats.map((threat) => buildThreatRow(threat, options))
	);
}

// Columns shared by both reports' "All Threats" table.
export function threatTableHeaders(options: { product?: boolean; description?: boolean }): {
	headers: string[];
	widths: any[];
} {
	const headers: string[] = ['Name'];
	const widths: any[] = ['auto'];
	if (options.product) {
		headers.push('Product');
		widths.push('auto');
	}
	if (options.description) {
		headers.push('Damage Description');
		widths.push('*');
	}
	headers.push('Probability', 'Assets at risk ($)', 'SLE ($)', 'Target mitigation', 'SLE after mitigation ($)');
	widths.push('auto', 'auto', 'auto', 'auto', 'auto');
	return { headers, widths };
}

function buildContent(options: RiskReportOptions): any[] {
	const { documentTitle, facts, sections, logoImage } = options;
	const monthYear = new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' });

	const content: any[] = [
		{
			columns: [
				logoImage
					? { width: '*', image: logoImage, fit: [150, 43] }
					: { width: '*', text: 'OpenCRO', fontSize: 24, bold: true, color: BRAND_COLOR },
				{
					width: 'auto',
					alignment: 'right',
					margin: [0, 16, 0, 0],
					text: TAGLINE,
					italics: true,
					fontSize: 11,
					color: VALUE_COLOR
				}
			],
			columnGap: 16
		},
		{ text: monthYear, bold: true, fontSize: 12, color: '#111111', margin: [0, 22, 0, 10] },
		{ text: DISCLAIMER, fontSize: 9.5, lineHeight: 1.3, color: '#444444', margin: [0, 0, 0, 26] },
		{ text: documentTitle, fontSize: 24, bold: true, color: '#111111', margin: [0, 0, 0, 18] }
	];

	if (facts.length > 0) {
		content.push({
			table: {
				widths: [150, '*'],
				body: facts.map(([label, value]) => [
					{ text: label, bold: true, color: LABEL_COLOR, fillColor: '#f7f9fa' },
					{ text: value, color: VALUE_COLOR }
				])
			},
			layout: TABLE_LAYOUT
		});
	}

	for (const section of sections) {
		content.push({
			text: section.heading,
			fontSize: 15,
			bold: true,
			color: TITLE_COLOR,
			margin: [0, 0, 0, 10],
			pageBreak: 'before'
		});
		if (section.chartImage) {
			content.push({ image: section.chartImage, width: 500, alignment: 'center', margin: [0, 0, 0, 12] });
		}
		content.push(section.table);
		content.push({ text: SLE_LEGEND, fontSize: 8.5, color: '#757575', margin: [0, 8, 0, 0] });
	}

	return content;
}

export function buildRiskReportDocDefinition(options: RiskReportOptions): any {
	const { logoImage } = options;
	const generatedOn = new Date().toLocaleDateString('en-US', {
		year: 'numeric',
		month: 'short',
		day: 'numeric'
	});

	return {
		pageSize: 'A4',
		pageMargins: [40, 52, 40, 55],
		// Page 1 carries the full OpenCRO block in the content; later pages get a slim band.
		header: (currentPage: number) => {
			if (currentPage === 1) return null;
			return {
				margin: [40, 10, 40, 0],
				columns: [
					logoImage
						? { width: '*', image: logoImage, fit: [90, 26] }
						: { width: '*', text: 'OpenCRO', fontSize: 13, bold: true, color: BRAND_COLOR },
					{
						width: 'auto',
						alignment: 'right',
						margin: [0, 8, 0, 0],
						text: TAGLINE,
						italics: true,
						fontSize: 8.5,
						color: '#999999'
					}
				]
			};
		},
		content: buildContent(options),
		footer: (currentPage: number, pageCount: number) => ({
			margin: [40, 10, 40, 0],
			columns: [
				{ text: `Generated ${generatedOn}`, color: '#999999', fontSize: 9 },
				{
					text: `Page ${currentPage} of ${pageCount}`,
					alignment: 'right',
					color: '#999999',
					fontSize: 9
				}
			]
		}),
		defaultStyle: { fontSize: 10, color: VALUE_COLOR }
	};
}

// -------------------------------------------------------------------------
// Model Risk report
// -------------------------------------------------------------------------

export interface ModelRiskPdfHeader {
	model_id: number;
	model_name: string;
	product: string;
	company: string;
	org_id?: number;
	sales?: number;
	funding?: number;
	valuation?: number;
	device_description?: string;
	intended_use?: string;
	competitive_advantage?: string;
	competitors?: string;
}

export interface ModelRiskPdfInput {
	header: ModelRiskPdfHeader | null;
	chartThreats: RiskThreat[];
	allThreats: RiskThreat[];
	chartImage: string | null;
	logoImage: string | null;
}

export function getModelRiskPdfFileName(
	header: ModelRiskPdfHeader | null,
	modelId: string | number
): string {
	const product = header?.product && header.product !== '-' ? header.product : null;
	const base = product || header?.model_name || `Model Risk ${modelId}`;
	const safe = base.replace(/[^a-z0-9]+/gi, '-').replace(/^-+|-+$/g, '');
	return `${safe || 'model-risk'}.pdf`;
}

export function buildModelRiskDocDefinition(data: ModelRiskPdfInput): any {
	const { header, chartThreats, allThreats, chartImage, logoImage } = data;

	const deviceName = header?.product && header.product !== '-' ? header.product : null;
	const documentTitle = `Risk Analysis: ${
		deviceName || header?.model_name || 'AI-enabled medical device'
	}`;

	const facts: Array<[string, string]> = [];
	if (header) {
		facts.push(
			['Model', header.model_name || '-'],
			['Company', header.company || '-'],
			['Sales', formatCurrency(header.sales)],
			['Funding', formatCurrency(header.funding)],
			['Valuation', formatCurrency(header.valuation)],
			['Product', header.product || '-'],
			['Competitive Advantage', header.competitive_advantage || '-'],
			['Competitors', header.competitors || '-']
		);
		if (header.device_description) facts.push(['Device Description', header.device_description]);
		if (header.intended_use) facts.push(['Intended Use', header.intended_use]);
	}

	const sections: RiskReportSection[] = [];
	if (chartThreats.length > 0) {
		sections.push({
			heading: 'Top 5 Single Loss Events (SLE)',
			chartImage,
			table: buildThreatTable(
				[
					'Threat',
					'Probability',
					'Assets at risk ($)',
					'SLE ($)',
					'Target mitigation',
					'SLE after mitigation ($)'
				],
				['*', 'auto', 'auto', 'auto', 'auto', 'auto'],
				chartThreats
			)
		});
	}
	if (allThreats.length > 0) {
		const all = threatTableHeaders({ description: true });
		sections.push({
			heading: 'All Threats',
			table: buildThreatTable(all.headers, all.widths, allThreats, { description: true })
		});
	}

	return buildRiskReportDocDefinition({ documentTitle, facts, sections, logoImage });
}

// -------------------------------------------------------------------------
// Enterprise Risk report
// -------------------------------------------------------------------------

export interface EnterpriseRiskPdfOrg {
	id?: number;
	name: string;
	funding?: number;
	estimated_annual_sales?: number;
	size?: number;
	tier?: number;
}

export interface EnterpriseRiskPdfInput {
	org: EnterpriseRiskPdfOrg | null;
	chartThreats: RiskThreat[];
	allThreats: RiskThreat[];
	chartImage: string | null;
	logoImage: string | null;
}

export function getEnterpriseRiskPdfFileName(org: EnterpriseRiskPdfOrg | null): string {
	const safe = (org?.name || 'enterprise-risk').replace(/[^a-z0-9]+/gi, '-').replace(/^-+|-+$/g, '');
	return `${safe || 'enterprise-risk'}.pdf`;
}

function orgTierLabel(tier?: number): string {
	if (tier === 1) return 'Enterprise';
	if (tier === 2) return 'Mid-Market';
	if (tier === 3) return 'Startup';
	return '-';
}

export function buildEnterpriseRiskDocDefinition(data: EnterpriseRiskPdfInput): any {
	const { org, chartThreats, allThreats, chartImage, logoImage } = data;

	const documentTitle = `Risk Analysis: ${org?.name || 'Enterprise'}`;

	const facts: Array<[string, string]> = org
		? [
				['Organization', org.name || '-'],
				['Funding', formatCurrency(org.funding)],
				['Estimated Annual Sales', formatCurrency(org.estimated_annual_sales)],
				['Valuation (Size)', formatCurrency(org.size)],
				['Tier', orgTierLabel(org.tier)]
			]
		: [];

	const sections: RiskReportSection[] = [];
	if (chartThreats.length > 0) {
		sections.push({
			heading: 'Top 5 Single Loss Events (SLE)',
			chartImage,
			table: buildThreatTable(
				[
					'Threat',
					'Probability',
					'Assets at risk ($)',
					'SLE ($)',
					'Target mitigation',
					'SLE after mitigation ($)'
				],
				['*', 'auto', 'auto', 'auto', 'auto', 'auto'],
				chartThreats
			)
		});
	}
	if (allThreats.length > 0) {
		const all = threatTableHeaders({ product: true, description: true });
		sections.push({
			heading: 'All Threats',
			table: buildThreatTable(all.headers, all.widths, allThreats, { product: true, description: true })
		});
	}

	return buildRiskReportDocDefinition({ documentTitle, facts, sections, logoImage });
}
