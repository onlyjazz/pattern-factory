import type { Experiment } from '$lib/types/models';

export type ExperimentArm = Experiment['arm'];
export type EmailHeaderStatus = Experiment['email_header_status'];

/** Minimal product shape used by the experiment membership picker. */
export interface ProductOption {
	id: number;
	name: string;
}

/** Experiment arm choices, in the order they appear in select boxes. */
export const ARM_OPTIONS: { value: ExperimentArm; label: string }[] = [
	{ value: 'social', label: 'Social' },
	{ value: 'risk-then-superiority', label: 'Risk then Superiority' },
	{ value: 'superiority-then-risk', label: 'Superiority then Risk' }
];

/** Email header review status choices. */
export const EMAIL_HEADER_STATUS_OPTIONS: EmailHeaderStatus[] = ['draft', 'approved'];

/** Human-readable label for an experiment arm value. */
export function armLabel(arm: string | null | undefined): string {
	return ARM_OPTIONS.find((option) => option.value === arm)?.label ?? arm ?? '-';
}
