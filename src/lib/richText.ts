import { marked } from 'marked';

/**
 * Helpers for rich text fields that are authored in RichTextEditor.
 *
 * Rich text is stored as HTML. Rows written before the editor existed hold
 * plain text or markdown, so reads fall back to a markdown render instead of
 * collapsing them into a single line.
 */

const HTML_MARKUP_PATTERN =
	/<(?:p|div|br|h[1-6]|strong|b|em|i|u|s|ul|ol|li|blockquote|a|hr|pre|code|span)\b[^>]*>/i;

const MARKDOWN_PATTERN =
	/(^|\n)\s{0,3}(?:#{1,6}\s|[-*+]\s|\d+\.\s|>\s|```|-{3,})|\*\*[^*\n]+\*\*|\[[^\]]+\]\([^)]+\)/;

/** LaTeX commands that appear in outreach templates and have a plain glyph. */
const LATEX_GLYPHS: Record<string, string> = {
	rightarrow: '→',
	to: '→',
	Rightarrow: '⇒',
	leftarrow: '←',
	mapsto: '↦'
};

const BLOCKED_TAGS = ['script', 'style', 'iframe', 'object', 'embed', 'form', 'input', 'link', 'meta'];

const URL_ATTRIBUTES = ['href', 'src', 'xlink:href'];

const NAMED_ENTITIES: Record<string, string> = {
	amp: '&',
	lt: '<',
	gt: '>',
	quot: '"',
	apos: "'",
	nbsp: ' '
};

/** Single newlines stay line breaks, matching how templates are written. */
const MARKDOWN_OPTIONS = { async: false, breaks: true, gfm: true };

/** True when a stored value already contains markup written by the rich text editor. */
export function looksLikeHtml(value: string): boolean {
	return HTML_MARKUP_PATTERN.test(value);
}

/** Replace `$\rightarrow$`-style LaTeX commands with the glyph they stand for. */
export function expandLatexGlyphs(text: string): string {
	return text.replace(/\$\\([a-zA-Z]+)\$/g, (match, command: string) => LATEX_GLYPHS[command] ?? match);
}

/** Render markdown to HTML. */
export function markdownToHtml(markdown: string): string {
	return marked.parse(expandLatexGlyphs(markdown), MARKDOWN_OPTIONS) as string;
}

/** True when pasted text carries markdown syntax worth converting. */
export function containsMarkdown(text: string): boolean {
	return MARKDOWN_PATTERN.test(text);
}

/** Strip executable markup from stored rich text. */
export function sanitizeHtml(html: string): string {
	if (typeof DOMParser === 'undefined') return stripMarkupByRegex(html);
	const doc = new DOMParser().parseFromString(html, 'text/html');
	doc.querySelectorAll(BLOCKED_TAGS.join(',')).forEach((element) => element.remove());
	doc.querySelectorAll('*').forEach((element) => {
		for (const attribute of Array.from(element.attributes)) {
			const name = attribute.name.toLowerCase();
			if (name.startsWith('on')) {
				element.removeAttribute(attribute.name);
			} else if (URL_ATTRIBUTES.includes(name) && /^\s*javascript:/i.test(attribute.value)) {
				element.removeAttribute(attribute.name);
			}
		}
	});
	return doc.body.innerHTML;
}

/** HTML for the read-only view: stored rich text as-is, legacy values via markdown. */
export function richTextToHtml(value: string | null | undefined): string {
	const source = (value ?? '').trim();
	if (source === '') return '';
	return sanitizeHtml(looksLikeHtml(source) ? source : markdownToHtml(source));
}

/** Plain text for search matching, so stored tags never match a query. */
export function richTextToPlain(value: string | null | undefined): string {
	const source = value ?? '';
	if (source === '' || !looksLikeHtml(source)) return source;
	return decodeEntities(stripMarkupByRegex(source).replace(/<[^>]*>/g, ' ')).replace(/\s+/g, ' ').trim();
}

function stripMarkupByRegex(html: string): string {
	const blocked = BLOCKED_TAGS.join('|');
	return html
		.replace(new RegExp(`<(${blocked})\\b[\\s\\S]*?</\\1>`, 'gi'), '')
		.replace(new RegExp(`<(${blocked})\\b[^>]*>`, 'gi'), '')
		.replace(/\son[a-z]+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '')
		.replace(/(href|src)\s*=\s*("[^"]*"|'[^']*')/gi, (match, _attribute, quoted: string) =>
			/^\s*javascript:/i.test(quoted.slice(1, -1)) ? '' : match
		);
}

function decodeEntities(text: string): string {
	return text.replace(/&(#x?[0-9a-f]+|[a-z]+);/gi, (match, entity: string) => {
		if (entity.startsWith('#')) {
			const hex = entity[1]?.toLowerCase() === 'x';
			const code = parseInt(hex ? entity.slice(2) : entity.slice(1), hex ? 16 : 10);
			return Number.isFinite(code) ? String.fromCodePoint(code) : match;
		}
		return NAMED_ENTITIES[entity.toLowerCase()] ?? match;
	});
}
