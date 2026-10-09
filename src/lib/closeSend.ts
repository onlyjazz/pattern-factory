import { API_BASE } from '$lib/config';

/** Result of activating an experiment (POST /experiments/{id}/start). */
export interface StartExperimentResult {
	success: number;
	failed: number;
	companies: number;
	contacts: number;
	errors: string[];
	smartViewError: string | null;
}

/** Parse a start-experiment response body into the UI result shape. */
export function parseStartResult(body: Record<string, unknown>): StartExperimentResult {
	const results = Array.isArray(body.results) ? (body.results as { error?: string | null }[]) : [];
	return {
		success: Number(body.success ?? 0),
		failed: Number(body.failed ?? 0),
		companies: Number(body.companies ?? 0),
		contacts: Number(body.contacts ?? 0),
		errors: results
			.map((r) => r?.error)
			.filter((e): e is string => typeof e === 'string' && e.length > 0),
		smartViewError: typeof body.smart_view_error === 'string' ? body.smart_view_error : null
	};
}

/** Activate an experiment for the given products; throws Error(detail) on failure. */
export async function startExperiment(
	experimentId: number,
	productIds: number[],
	apiBase: string = API_BASE
): Promise<StartExperimentResult> {
	const response = await fetch(`${apiBase}/experiments/${experimentId}/start`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ product_ids: productIds })
	});
	if (!response.ok) {
		let detail = 'Failed to start experiment';
		try {
			const errBody = await response.json();
			if (errBody?.detail) {
				detail = typeof errBody.detail === 'string' ? errBody.detail : JSON.stringify(errBody.detail);
			}
		} catch {
			// keep the generic message
		}
		throw new Error(detail);
	}
	const body: Record<string, unknown> = await response.json();
	return parseStartResult(body);
}
