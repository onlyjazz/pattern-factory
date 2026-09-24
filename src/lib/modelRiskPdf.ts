/**
 * Builds the pdfmake document definition for the Model Risk page export.
 *
 * This module is intentionally free of DOM/browser APIs (the chart is
 * rasterized by the caller and passed in as a data URL) so the document
 * definition can be reused and smoke-tested outside the browser.
 */

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

export interface ModelRiskPdfThreat {
	threat_name?: string;
	damage_description?: string;
	gross_sle?: number;
	target_sle?: number;
	target_mitigation_pct?: number;
}

export interface ModelRiskPdfInput {
	header: ModelRiskPdfHeader | null;
	chartThreats: ModelRiskPdfThreat[];
	allThreats: ModelRiskPdfThreat[];
	chartImage: string | null;
}

const BRAND_COLOR = '#039be5';
const TITLE_COLOR = '#263238';
const LABEL_COLOR = '#666666';
const VALUE_COLOR = '#333333';
const TABLE_BORDER = '#e0e0e0';

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

export function formatCurrency(value?: number): string {
	if (value === undefined || value === null) return '-';
	return new Intl.NumberFormat('en-US', {
		style: 'currency',
		currency: 'USD',
		maximumFractionDigits: 0
	}).format(value);
}

export function formatNumber(value?: number): string {
	if (value === undefined || value === null) return '-';
	return value.toLocaleString('en-US');
}

export function formatPercent(value?: number): string {
	if (value === undefined || value === null) return '-';
	return `${value.toFixed(1)}%`;
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
	const { header, chartThreats, allThreats, chartImage } = data;

	const buildTable = (headers: string[], widths: any[], rows: any[][]) => ({
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
	});

	const factRows: Array<[string, string]> = [];
	if (header) {
		factRows.push(
			['Model', header.model_name || '-'],
			['Company', header.company || '-'],
			['Sales', formatCurrency(header.sales)],
			['Funding', formatCurrency(header.funding)],
			['Valuation', formatCurrency(header.valuation)],
			['Product', header.product || '-'],
			['Competitive Advantage', header.competitive_advantage || '-'],
			['Competitors', header.competitors || '-']
		);
		if (header.device_description) factRows.push(['Device Description', header.device_description]);
		if (header.intended_use) factRows.push(['Intended Use', header.intended_use]);
	}

	const factsTable = {
		table: {
			widths: [150, '*'],
			body: factRows.map(([label, value]) => [
				{ text: label, bold: true, color: LABEL_COLOR, fillColor: '#f7f9fa' },
				{ text: value, color: VALUE_COLOR }
			])
		},
		layout: TABLE_LAYOUT
	};

	const summaryTable = buildTable(
		['Threat', 'Gross SLE', 'Target SLE', 'Target Mitigation %'],
		['*', 'auto', 'auto', 'auto'],
		chartThreats.map((t) => [
			{ text: t.threat_name || '-', color: VALUE_COLOR },
			{ text: formatNumber(t.gross_sle), alignment: 'center', color: VALUE_COLOR },
			{ text: formatNumber(t.target_sle), alignment: 'center', color: VALUE_COLOR },
			{ text: formatPercent(t.target_mitigation_pct), alignment: 'center', color: VALUE_COLOR }
		])
	);

	const threatsTable = buildTable(
		['Name', 'Damage Description', 'Gross SLE', 'Target SLE', 'Target Mitigation %'],
		['auto', '*', 'auto', 'auto', 'auto'],
		allThreats.map((t) => [
			{ text: t.threat_name || '-', color: VALUE_COLOR },
			{ text: t.damage_description || '-', color: VALUE_COLOR },
			{ text: formatNumber(t.gross_sle), alignment: 'center', color: VALUE_COLOR },
			{ text: formatNumber(t.target_sle), alignment: 'center', color: VALUE_COLOR },
			{ text: formatPercent(t.target_mitigation_pct), alignment: 'center', color: VALUE_COLOR }
		])
	);

	const content: any[] = [
		{ text: 'Model Risk', fontSize: 26, bold: true, color: TITLE_COLOR, margin: [0, 0, 0, 2] },
		{
			text: 'Top 5 Single Loss Events (SLE)',
			fontSize: 12,
			color: LABEL_COLOR,
			margin: [0, 0, 0, 16]
		}
	];

	if (factRows.length > 0) {
		content.push(factsTable);
	}

	if (chartThreats.length > 0) {
		content.push({
			text: 'Top 5 Single Loss Events (SLE)',
			fontSize: 15,
			bold: true,
			color: TITLE_COLOR,
			margin: [0, 0, 0, 10],
			pageBreak: 'before'
		});
		if (chartImage) {
			content.push({ image: chartImage, width: 500, alignment: 'center', margin: [0, 0, 0, 12] });
		}
		content.push(summaryTable);
	}

	if (allThreats.length > 0) {
		content.push({
			text: 'All Threats',
			fontSize: 15,
			bold: true,
			color: TITLE_COLOR,
			margin: [0, 0, 0, 10],
			pageBreak: 'before'
		});
		content.push(threatsTable);
	}

	const generatedOn = new Date().toLocaleDateString('en-US', {
		year: 'numeric',
		month: 'short',
		day: 'numeric'
	});

	return {
		pageSize: 'A4',
		pageMargins: [40, 80, 40, 55],
		header: () => ({
			table: {
				widths: ['*'],
				body: [
					[
						{
							text: header
								? `Pattern Factory   |   Model Risk — ${header.product}`
								: 'Pattern Factory   |   Model Risk',
							color: '#ffffff',
							fontSize: 12,
							margin: [40, 14, 40, 14],
							fillColor: BRAND_COLOR
						}
					]
				]
			},
			layout: 'noBorders'
		}),
		content,
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
