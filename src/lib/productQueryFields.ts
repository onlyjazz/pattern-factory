import type { Product } from './db';
import type { FieldSpec } from './queryFilter';

/**
 * A product row as rendered on the products index: the API row plus the org
 * fields the page joins in client-side so they can be sorted and filtered.
 */
export type ProductRow = Product & {
	org_name: string | null;
	arm: number | null;
	tier: number | null;
	size: number | null;
};

/**
 * Columns the products index exposes to the lite SQL filter, e.g.
 * `panel = Radiology`, `org like Hologic`, `valuation between 10M and 200M`.
 *
 * `valuation` maps to `orgs.size`, the column the products and orgs tables
 * already label "Valuation".
 */
export const productQueryFields: FieldSpec<ProductRow>[] = [
	{ key: 'device', label: 'Device', type: 'text', aliases: ['device'], get: (row) => row.device },
	{
		key: 'submission_number',
		label: 'Submission number',
		type: 'text',
		aliases: ['submission', 'submission number', 'submission_number'],
		get: (row) => row.submission_number
	},
	{ key: 'panel', label: 'Panel', type: 'text', aliases: ['panel'], get: (row) => row.panel },
	{ key: 'tag', label: 'Tag', type: 'text', aliases: ['tag'], get: (row) => row.tag },
	{
		key: 'date_of_final_decision',
		label: 'Final decision',
		type: 'date',
		aliases: [
			'final decision',
			'final decision date',
			'date_of_final_decision',
			'final_decision',
			'decision'
		],
		get: (row) => row.date_of_final_decision
	},
	{
		key: 'close_send_date',
		label: 'Close send date',
		type: 'date',
		aliases: ['close send', 'close send date', 'close_send_date', 'close_send'],
		get: (row) => row.close_send_date
	},
	{
		key: 'close_sent',
		label: 'Close sent',
		type: 'boolean',
		aliases: ['close sent', 'close_sent', 'sent'],
		get: (row) => row.close_sent
	},
	{
		key: 'intended_use',
		label: 'Intended use',
		type: 'text',
		aliases: ['intended use', 'intended_use'],
		get: (row) => row.intended_use
	},
	{
		key: 'indications_for_use',
		label: 'Indications for use',
		type: 'text',
		aliases: ['indications for use', 'indications_for_use', 'indications', 'indication'],
		get: (row) => row.indications_for_use
	},
	{
		key: 'device_description',
		label: 'Device description',
		type: 'text',
		aliases: ['device description', 'device_description', 'description'],
		get: (row) => row.device_description
	},
	{
		key: 'superiority',
		label: 'Superiority',
		type: 'text',
		aliases: ['superiority'],
		get: (row) => row.superiority
	},
	{
		key: 'competitors',
		label: 'Competitors',
		type: 'text',
		aliases: ['competitors', 'competitor'],
		get: (row) => row.competitors
	},
	{
		key: 'primary_product_code',
		label: 'Product code',
		type: 'text',
		aliases: ['primary product code', 'primary_product_code', 'product code', 'product_code'],
		get: (row) => row.primary_product_code
	},
	{
		key: 'process_flag',
		label: 'Process flag',
		type: 'boolean',
		aliases: ['process flag', 'process_flag'],
		get: (row) => row.process_flag
	},
	{
		key: 'updated_at',
		label: 'Updated',
		type: 'date',
		aliases: ['updated', 'updated at', 'updated_at'],
		get: (row) => row.updated_at
	},
	{
		key: 'created_at',
		label: 'Created',
		type: 'date',
		aliases: ['created', 'created at', 'created_at'],
		get: (row) => row.created_at
	},
	{
		key: 'org_name',
		label: 'Org',
		type: 'text',
		aliases: ['org', 'org name', 'org_name', 'organization', 'organisation', 'company'],
		get: (row) => row.org_name ?? row.company
	},
	{
		key: 'size',
		label: 'Valuation',
		type: 'number',
		aliases: ['valuation', 'size'],
		get: (row) => row.size
	},
	{
		key: 'sle_after_mitigation',
		label: 'SLE after mitigation',
		type: 'number',
		aliases: ['sle', 'sle after mitigation', 'sle_after_mitigation'],
		get: (row) => row.sle_after_mitigation
	},
	{ key: 'arm', label: 'Arm', type: 'number', aliases: ['arm'], get: (row) => row.arm },
	{ key: 'tier', label: 'Tier', type: 'number', aliases: ['tier'], get: (row) => row.tier }
];
