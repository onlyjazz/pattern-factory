/**
 * Lite SQL-style filtering for index pages.
 *
 * Turns the contents of the global search box into a filter — `panel = Radiology`,
 * `org like Hologic`, `valuation between 10M and 200M`, `final decision after 2025`,
 * `arm = 2 and not sent` — and evaluates it against rows that are already held in
 * memory, so no backend or query-param changes are needed.
 *
 * A string only becomes a filter when it starts with a known field alias followed
 * by a recognized operator. Everything else is handed back as `{ kind: 'text' }`
 * so the caller keeps its existing substring search.
 *
 * When such a string looks like a condition but names a column we don't know
 * (`panell = Radiology`), the text result carries a `warning` naming the closest
 * known column — otherwise a typo reads as "no matches" instead of
 * "unrecognized column".
 *
 * Scope for this release: clauses joined by `and`, each optionally prefixed with
 * `not` (`not sent`, `not panel = Radiology`). No `or`, no parentheses.
 */

export type FieldType = 'text' | 'number' | 'date' | 'boolean';

export interface FieldSpec<Row> {
	/** Stable column identifier, used for labels and tests. */
	key: string;
	/** Human-readable column name shown in the filter summary. */
	label: string;
	/**
	 * Accepted spellings for this column. Matching is case-insensitive and
	 * treats `_` and spaces as equivalent.
	 */
	aliases: string[];
	type: FieldType;
	get: (row: Row) => unknown;
}

export type Operator = '=' | '!=' | '>' | '<' | '>=' | '<=' | 'like' | 'between';

/**
 * A resolved date value. A bare year or month covers a whole period rather
 * than a single instant, so `= 2025` means "sometime in 2025".
 */
export interface DatePeriod {
	start: Date;
	end: Date;
}

export type ConditionValue = string | number | boolean | DatePeriod;

export interface Condition<Row> {
	field: FieldSpec<Row>;
	operator: Operator;
	/** Operator exactly as typed (e.g. `after`), for the summary label. */
	operatorText: string;
	values: ConditionValue[];
	/** Value text exactly as typed, for the summary label. */
	valueTexts: string[];
}

/** One `and`-joined piece of a filter, optionally negated. */
export interface Clause<Row> {
	condition: Condition<Row>;
	/** True when the clause was written with a leading `not`. */
	negated: boolean;
	/** Human-readable form of this clause, e.g. `Panel = Radiology` or `NOT Close sent`. */
	label: string;
}

export interface Filter<Row> {
	clauses: Clause<Row>[];
	/** Human-readable form of the whole filter, clauses joined by ` AND `. */
	label: string;
}

export type Query<Row = unknown> =
	| { kind: 'text'; term: string; warning?: string }
	| { kind: 'filter'; filter: Filter<Row> }
	| { kind: 'error'; message: string };

/** Word operators are matched before symbols so `between` wins over `=`. */
const WORD_OPERATOR_PATTERN = /^(between|like|contains|after|before)\b\s*([\s\S]*)$/i;
const SYMBOL_OPERATOR_PATTERN = /^(>=|<=|<>|!=|=|>|<)\s*([\s\S]*)$/;
const AND_SEPARATOR_PATTERN = /^and(?:\s|$)/i;
const AND_PREFIX_PATTERN = /^and\b\s*/i;
const NOT_PREFIX_PATTERN = /^not\b\s*/i;
const MAGNITUDES: Record<string, number> = { k: 1e3, m: 1e6, b: 1e9, t: 1e12 };

const aliasPatternCache = new Map<string, RegExp>();

/**
 * Parses `input` against `fields`. Never throws: anything unusable comes back
 * as a text term (not a filter) or as an error with a specific reason.
 */
export function parseQuery<Row>(input: string, fields: FieldSpec<Row>[]): Query<Row> {
	const text = (input ?? '').trim();
	if (!text) return { kind: 'text', term: '' };

	const clauses: Clause<Row>[] = [];
	let rest = text;

	for (;;) {
		const parsed = parseClause(rest, fields);

		if (parsed.status === 'error') return { kind: 'error', message: parsed.message };

		if (parsed.status === 'none') {
			// A first clause that does not parse is an ordinary search. A later
			// one means the user started a filter and it went wrong.
			if (clauses.length === 0) {
				const warning = columnWarning(text, fields);
				return warning ? { kind: 'text', term: text, warning } : { kind: 'text', term: text };
			}
			return { kind: 'error', message: unreadableClauseMessage(rest, fields) };
		}

		clauses.push(parsed.clause);
		rest = parsed.rest;
		if (!rest) break;

		const separator = AND_PREFIX_PATTERN.exec(rest);
		if (!separator) {
			return { kind: 'error', message: `Expected "and" before "${rest}"` };
		}
		rest = rest.slice(separator[0].length).trim();
		if (!rest) {
			return {
				kind: 'error',
				message: '"and" needs a second condition, e.g. panel = Radiology and not sent'
			};
		}
	}

	return { kind: 'filter', filter: { clauses, label: clauses.map((c) => c.label).join(' AND ') } };
}

/** Applies a parsed filter to a single row: every clause must match. */
export function matchesFilter<Row>(filter: Filter<Row>, row: Row): boolean {
	return filter.clauses.every((clause) => {
		const matched = matchesCondition(clause.condition, row);
		return clause.negated ? !matched : matched;
	});
}

/** Applies a single condition to a row. */
export function matchesCondition<Row>(condition: Condition<Row>, row: Row): boolean {
	const cell = condition.field.get(row);
	switch (condition.field.type) {
		case 'text':
			return compareText(cell, condition.operator, condition.values as string[]);
		case 'number':
			return compareNumber(cell, condition.operator, condition.values as number[]);
		case 'date':
			return compareDate(cell, condition.operator, condition.values as DatePeriod[]);
		case 'boolean':
			return compareBoolean(cell, condition.operator, condition.values as boolean[]);
		default:
			return false;
	}
}

type ClauseParse<Row> =
	| { status: 'ok'; clause: Clause<Row>; rest: string }
	| { status: 'error'; message: string }
	/** The text is not a clause at all, so it may just be a search term. */
	| { status: 'none' };

/** Parses `[not] <column> <operator> <value>` off the front of `text`. */
function parseClause<Row>(text: string, fields: FieldSpec<Row>[]): ClauseParse<Row> {
	let rest = text.trim();
	let negated = false;

	const notMatch = NOT_PREFIX_PATTERN.exec(rest);
	if (notMatch) {
		negated = true;
		rest = rest.slice(notMatch[0].length).trim();
		if (!rest) {
			return {
				status: 'error',
				message: '"not" needs a condition, e.g. not sent or not panel = Radiology'
			};
		}
	}

	const match = matchFieldAlias(rest, fields);
	if (!match) {
		if (!negated) return { status: 'none' };
		const unknown = suggestColumn(rest, fields);
		return {
			status: 'error',
			message: unknown
				? `No column named "${unknown.head}" — did you mean "${unknown.alias}"?`
				: `Can't read "${rest}" as a condition after "not"`
		};
	}

	const remainder = rest.slice(match.consumed).trim();
	const parsed = parseCondition(remainder, match.field);

	if (parsed.status === 'error') return { status: 'error', message: parsed.message };

	if (parsed.status === 'none') {
		// A bare column only means something as a boolean negation: `not sent`.
		if (!negated) return { status: 'none' };
		if (match.field.type !== 'boolean') {
			const column = match.field.label.toLowerCase();
			return {
				status: 'error',
				message: `"not ${column}" needs a boolean column, or an operator such as "${column} = ..."`
			};
		}
		return {
			status: 'ok',
			clause: {
				condition: {
					field: match.field,
					operator: '=',
					operatorText: '=',
					values: [true],
					valueTexts: ['true']
				},
				negated: true,
				label: `NOT ${match.field.label}`
			},
			rest: remainder
		};
	}

	return {
		status: 'ok',
		clause: {
			condition: parsed.condition,
			negated,
			label: negated ? `NOT (${parsed.label})` : parsed.label
		},
		rest: parsed.rest
	};
}

type ConditionParse<Row> =
	| { status: 'ok'; condition: Condition<Row>; label: string; rest: string }
	| { status: 'error'; message: string }
	/** No operator follows, so this is not a condition. */
	| { status: 'none' };

/**
 * Parses `<operator> <value>` off the front of `rest`. The value stops at the
 * first top-level ` and ` so the remainder can be parsed as the next clause;
 * `between` consumes its own `and` before looking for that separator.
 */
function parseCondition<Row>(rest: string, field: FieldSpec<Row>): ConditionParse<Row> {
	const text = rest.trim();
	if (!text) return { status: 'none' };

	let operatorText: string;
	let valueText: string;
	const wordMatch = WORD_OPERATOR_PATTERN.exec(text);
	if (wordMatch) {
		operatorText = wordMatch[1].toLowerCase();
		valueText = wordMatch[2].trim();
	} else {
		const symbolMatch = SYMBOL_OPERATOR_PATTERN.exec(text);
		if (!symbolMatch) return { status: 'none' };
		operatorText = symbolMatch[1];
		valueText = symbolMatch[2].trim();
	}

	const operator = toOperator(operatorText);

	let rawValues: string[];
	let remainder: string;
	if (operator === 'between') {
		const firstIndex = findAndSeparator(valueText);
		if (firstIndex < 0) {
			return {
				status: 'error',
				message: '"between" needs two values joined by "and", e.g. valuation between 10M and 200M'
			};
		}
		const afterFirst = stripAndPrefix(valueText.slice(firstIndex));
		const secondIndex = findAndSeparator(afterFirst);
		rawValues = [
			valueText.slice(0, firstIndex).trim(),
			secondIndex < 0 ? afterFirst.trim() : afterFirst.slice(0, secondIndex).trim()
		];
		remainder = secondIndex < 0 ? '' : afterFirst.slice(secondIndex).trim();
	} else {
		const index = findAndSeparator(valueText);
		rawValues = [index < 0 ? valueText : valueText.slice(0, index).trim()];
		remainder = index < 0 ? '' : valueText.slice(index).trim();
	}
	rawValues = rawValues.map(stripQuotes);

	if (rawValues.some((value) => value === '')) {
		return { status: 'error', message: `Missing value for ${field.label.toLowerCase()}` };
	}

	const values: ConditionValue[] = [];
	for (const raw of rawValues) {
		const coerced = coerceValue(field, raw);
		if (!coerced.ok) return { status: 'error', message: coerced.message };
		values.push(coerced.value);
	}

	return {
		status: 'ok',
		condition: { field, operator, operatorText, values, valueTexts: rawValues },
		label: `${field.label} ${operatorText} ${rawValues.join(' and ')}`,
		rest: remainder
	};
}

type CoercionResult = { ok: true; value: ConditionValue } | { ok: false; message: string };

function coerceValue<Row>(field: FieldSpec<Row>, raw: string): CoercionResult {
	switch (field.type) {
		case 'text':
			return { ok: true, value: raw };
		case 'number': {
			const parsed = parseMagnitude(raw);
			if (parsed === null) {
				return { ok: false, message: `"${raw}" is not a number (try 10M, 200M, 1.5B)` };
			}
			return { ok: true, value: parsed };
		}
		case 'date': {
			const period = parseDatePeriod(raw);
			if (!period) {
				return { ok: false, message: `"${raw}" is not a date (try 2025, 2025-06, 2025-06-30)` };
			}
			return { ok: true, value: period };
		}
		case 'boolean': {
			const parsed = parseBoolean(raw);
			if (parsed === null) {
				return { ok: false, message: `"${raw}" is not true or false` };
			}
			return { ok: true, value: parsed };
		}
		default:
			return { ok: false, message: `"${raw}" is not supported` };
	}
}

/** Returns the longest alias matching the start of `text`. */
function matchFieldAlias<Row>(
	text: string,
	fields: FieldSpec<Row>[]
): { field: FieldSpec<Row>; consumed: number } | null {
	const candidates: { field: FieldSpec<Row>; alias: string }[] = [];
	for (const field of fields) {
		for (const alias of field.aliases) {
			const normalized = normalizeAlias(alias);
			if (normalized) candidates.push({ field, alias: normalized });
		}
	}
	// Longest alias first, so `final decision` is never read as `decision`.
	candidates.sort((a, b) => b.alias.length - a.alias.length);

	for (const { field, alias } of candidates) {
		const match = aliasPattern(alias).exec(text);
		if (match) return { field, consumed: match[0].length };
	}
	return null;
}

function compareText(cell: unknown, operator: Operator, values: string[]): boolean {
	const text = cell === null || cell === undefined ? '' : String(cell).toLowerCase();
	const a = values[0].toLowerCase();
	const b = values[1]?.toLowerCase() ?? a;
	switch (operator) {
		case '=':
			return text === a;
		case '!=':
			return text !== a;
		case 'like':
			return text.includes(a);
		case '>':
			return text > a;
		case '<':
			return text < a;
		case '>=':
			return text >= a;
		case '<=':
			return text <= a;
		case 'between':
			return text >= a && text <= b;
		default:
			return false;
	}
}

function compareNumber(cell: unknown, operator: Operator, values: number[]): boolean {
	if (cell === null || cell === undefined || cell === '') return false;
	const value = Number(cell);
	if (!Number.isFinite(value)) return false;
	const a = values[0];
	const b = values[1] ?? a;
	switch (operator) {
		case '=':
			return value === a;
		case '!=':
			return value !== a;
		case '>':
			return value > a;
		case '<':
			return value < a;
		case '>=':
			return value >= a;
		case '<=':
			return value <= a;
		case 'between':
			return value >= a && value <= b;
		case 'like':
			return String(value).includes(String(a));
		default:
			return false;
	}
}

function compareDate(cell: unknown, operator: Operator, values: DatePeriod[]): boolean {
	const date = toDate(cell);
	if (!date) return false;
	const a = values[0];
	const b = values[1] ?? a;
	switch (operator) {
		case '=':
			return date >= a.start && date <= a.end;
		case '!=':
			return !(date >= a.start && date <= a.end);
		case '>':
			// A bare year means the whole year, so `> 2025` starts in 2026.
			return date > a.end;
		case '<':
			return date < a.start;
		case '>=':
			// `after 2025` therefore includes all of 2025.
			return date >= a.start;
		case '<=':
			return date <= a.end;
		case 'between':
			return date >= a.start && date <= b.end;
		default:
			return false;
	}
}

function compareBoolean(cell: unknown, operator: Operator, values: boolean[]): boolean {
	if (typeof cell !== 'boolean') return false;
	switch (operator) {
		case '=':
			return cell === values[0];
		case '!=':
			return cell !== values[0];
		default:
			return false;
	}
}

function toOperator(text: string): Operator {
	switch (text.toLowerCase()) {
		case 'after':
			return '>=';
		case 'before':
			return '<';
		case 'contains':
			return 'like';
		case '<>':
			return '!=';
		default:
			return text as Operator;
	}
}

function normalizeAlias(alias: string): string {
	return alias.toLowerCase().replace(/_/g, ' ').replace(/\s+/g, ' ').trim();
}

/**
 * Anchored, case-insensitive pattern for a field alias. Spaces in the alias
 * accept either a space or an underscore, and the match must end at a word
 * boundary or at an operator character so `org` does not match `organization`.
 */
function aliasPattern(alias: string): RegExp {
	let pattern = aliasPatternCache.get(alias);
	if (!pattern) {
		const body = alias.split(' ').map(escapeRegExp).join('[\\s_]+');
		pattern = new RegExp(`^${body}(?=[\\s_=<>!]|$)`, 'i');
		aliasPatternCache.set(alias, pattern);
	}
	return pattern;
}

function escapeRegExp(value: string): string {
	return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Index of the whitespace before the first top-level ` and `, or -1. Quoted
 * spans are skipped so `org = 'Acme and Co'` is not split, and `and` must be a
 * whole word so `android` and `Andromeda` are safe.
 */
function findAndSeparator(text: string): number {
	let quote: string | null = null;
	for (let i = 0; i < text.length; i += 1) {
		const char = text[i];
		if (quote) {
			if (char === quote) quote = null;
			continue;
		}
		if (char === '"' || char === "'") {
			quote = char;
			continue;
		}
		if (char === ' ' && AND_SEPARATOR_PATTERN.test(text.slice(i + 1))) return i;
	}
	return -1;
}

/** Drops a leading `and` (plus its trailing space) from `text`. */
function stripAndPrefix(text: string): string {
	const match = AND_PREFIX_PATTERN.exec(text.trim());
	return match ? text.trim().slice(match[0].length) : text.trim();
}

/**
 * Matches `<column> <operator>` at the start of a string, for either symbol or
 * word operators, and captures the column part. Word operators need a space
 * before them so `devicelike` is not read as an operator.
 */
const CONDITION_SHAPE =
	/^([A-Za-z0-9_][A-Za-z0-9_ ]{0,40}?)\s*(?:>=|<=|<>|!=|=|>|<)\s*\S|^([A-Za-z0-9_][A-Za-z0-9_ ]{0,40}?)\s+(?:between|like|contains|after|before)\b/i;

/**
 * Returns the column-looking part of a string that was not understood as a
 * condition, or null when the string does not look like a condition at all.
 */
function conditionHead(text: string): string | null {
	const match = CONDITION_SHAPE.exec(text);
	if (!match) return null;
	const head = (match[1] ?? match[2] ?? '').trim().replace(/_/g, ' ').replace(/\s+/g, ' ');
	if (!head) return null;
	// Field aliases are at most three words; anything longer is prose.
	return head.split(' ').length > 3 ? null : head;
}

/**
 * Explains a clause that could not be read. A bare column is the common miss
 * (`and sent`), so that case names the operator to add instead of just
 * complaining.
 */
function unreadableClauseMessage<Row>(rest: string, fields: FieldSpec<Row>[]): string {
	const aliasMatch = matchFieldAlias(rest, fields);
	if (aliasMatch && !rest.slice(aliasMatch.consumed).trim()) {
		const column = aliasMatch.field.label.toLowerCase();
		return aliasMatch.field.type === 'boolean'
			? `"${rest}" needs an operator — try "${column} = true" or "not ${column}"`
			: `"${rest}" needs an operator, e.g. "${column} = ..."`;
	}

	const unknown = suggestColumn(rest, fields);
	if (unknown) return `No column named "${unknown.head}" — did you mean "${unknown.alias}"?`;
	return `Can't read "${rest}" as a condition after "and"`;
}

/**
 * Closest known column alias to a normalized target, or null when nothing is
 * near. Requires a near miss or a prefix relationship so unrelated words do
 * not produce nonsense suggestions.
 */
function closestAlias<Row>(target: string, fields: FieldSpec<Row>[]): string | null {
	if (target.length < 3) return null;
	const threshold = target.length <= 4 ? 1 : 2;

	let best: { alias: string; distance: number } | null = null;
	for (const field of fields) {
		for (const alias of field.aliases) {
			const normalized = normalizeAlias(alias);
			const distance = levenshtein(target, normalized);
			const isPrefix = normalized.startsWith(target) || target.startsWith(normalized);
			if (distance > threshold && !isPrefix) continue;
			if (!best || distance < best.distance) best = { alias, distance };
		}
	}

	return best?.alias ?? null;
}

/** Closest known column alias for the column-looking part of `text`. */
function suggestColumn<Row>(
	text: string,
	fields: FieldSpec<Row>[]
): { head: string; alias: string } | null {
	const head = conditionHead(text);
	if (!head) return null;
	const alias = closestAlias(normalizeAlias(head), fields);
	return alias ? { head, alias } : null;
}

/**
 * Warning for input that reads like a condition but names an unknown column.
 *
 * A first clause that fails to parse silently falls back to substring search,
 * which looks like "your filter matched nothing" rather than "I did not
 * understand the column". So this fires whenever there is a concrete
 * correction to offer, or whenever the string is clearly a filter attempt
 * (it contains an `and`). Plain searches stay quiet.
 */
function columnWarning<Row>(text: string, fields: FieldSpec<Row>[]): string | null {
	const head = conditionHead(text);
	if (!head) return null;

	const alias = closestAlias(normalizeAlias(head), fields);
	if (!alias && findAndSeparator(text) < 0) return null;

	const reason = alias
		? `No column named "${head}" — did you mean "${alias}"?`
		: `No column named "${head}".`;
	return `${reason} Showing text results instead.`;
}

/** Two-row Levenshtein distance, used for the "did you mean" suggestion. */
function levenshtein(a: string, b: string): number {
	const cols = b.length + 1;
	let previous = new Array<number>(cols);
	let current = new Array<number>(cols);
	for (let j = 0; j < cols; j += 1) previous[j] = j;

	for (let i = 1; i <= a.length; i += 1) {
		current[0] = i;
		for (let j = 1; j < cols; j += 1) {
			const cost = a[i - 1] === b[j - 1] ? 0 : 1;
			current[j] = Math.min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost);
		}
		const swap = previous;
		previous = current;
		current = swap;
	}

	return previous[cols - 1];
}

function stripQuotes(raw: string): string {
	const text = raw.trim();
	if (text.length < 2) return text;
	const first = text[0];
	const last = text[text.length - 1];
	if ((first === '"' && last === '"') || (first === "'" && last === "'")) {
		return text.slice(1, -1);
	}
	return text;
}

function parseMagnitude(raw: string): number | null {
	const text = raw.replace(/[$,\s]/g, '');
	const match = /^(-?\d+(?:\.\d+)?)([kmbt])?$/i.exec(text);
	if (!match) return null;
	const suffix = match[2]?.toLowerCase();
	const multiplier = suffix ? (MAGNITUDES[suffix] ?? 1) : 1;
	return Number(match[1]) * multiplier;
}

function parseBoolean(raw: string): boolean | null {
	const text = raw.trim().toLowerCase();
	if (text === 'true' || text === 'yes' || text === 'y' || text === '1') return true;
	if (text === 'false' || text === 'no' || text === 'n' || text === '0') return false;
	return null;
}

/**
 * Resolves a typed date into the period it covers: `2025` is the whole year,
 * `2025-06` the whole month, `2025-06-30` a single day.
 */
function parseDatePeriod(raw: string): DatePeriod | null {
	const text = raw.trim();

	const yearMatch = /^(\d{4})$/.exec(text);
	if (yearMatch) {
		const year = Number(yearMatch[1]);
		return { start: new Date(year, 0, 1), end: endOfDay(new Date(year, 11, 31)) };
	}

	const monthMatch = /^(\d{4})-(\d{1,2})$/.exec(text);
	if (monthMatch) {
		const year = Number(monthMatch[1]);
		const month = Number(monthMatch[2]) - 1;
		if (month < 0 || month > 11) return null;
		// Day 0 of the following month is the last day of this one.
		return { start: new Date(year, month, 1), end: endOfDay(new Date(year, month + 1, 0)) };
	}

	const dayMatch = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(text);
	if (dayMatch) {
		const year = Number(dayMatch[1]);
		const month = Number(dayMatch[2]) - 1;
		const day = Number(dayMatch[3]);
		const date = new Date(year, month, day);
		if (Number.isNaN(date.getTime()) || date.getMonth() !== month) return null;
		return { start: date, end: endOfDay(date) };
	}

	return null;
}

/**
 * Normalizes a stored value into a local Date. Products store
 * `date_of_final_decision` as text (`2026-03-30 00:00:00`), which is why the
 * date components are read directly instead of relying on `new Date(string)`.
 */
function toDate(value: unknown): Date | null {
	if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
	if (typeof value === 'number') {
		const fromNumber = new Date(value);
		return Number.isNaN(fromNumber.getTime()) ? null : fromNumber;
	}
	if (typeof value !== 'string') return null;

	const text = value.trim();
	if (!text) return null;

	const parts = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?/.exec(text);
	if (parts) {
		return new Date(
			Number(parts[1]),
			Number(parts[2]) - 1,
			Number(parts[3]),
			Number(parts[4] ?? 0),
			Number(parts[5] ?? 0),
			Number(parts[6] ?? 0)
		);
	}

	const parsed = new Date(text);
	return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function endOfDay(date: Date): Date {
	return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 23, 59, 59, 999);
}
