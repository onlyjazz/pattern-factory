<script lang="ts">
	import { onMount } from 'svelte';
	import 'quill/dist/quill.snow.css';
	import { BlockEmbed } from 'quill/blots/block';
	import { containsMarkdown, looksLikeHtml, markdownToHtml } from '$lib/richText';
	import type Quill from 'quill';
	import type { Delta } from 'quill';

	// Quill ships no horizontal-rule format, so a `---` separator in a pasted
	// template needs a blot before it survives the paste conversion.
	class DividerBlot extends BlockEmbed {
		static blotName = 'divider';
		static tagName = 'hr';
	}

	export let value: string | null | undefined = '';
	export let label = '';
	export let placeholder = '';
	export let compact = false;

	/** Only the formatting outreach templates actually use. */
	const TOOLBAR = [
		[{ header: [1, 2, 3, false] }],
		['bold', 'italic', 'underline', 'strike'],
		[{ list: 'ordered' }, { list: 'bullet' }],
		['blockquote', 'link'],
		['clean']
	];

	let editorElement: HTMLDivElement | undefined;
	let quill: Quill | null = null;
	let lastEmitted = '';
	let applyingExternalValue = false;

	$: normalizedValue = value ?? '';
	$: if (quill && normalizedValue !== lastEmitted) {
		applyValue(quill, normalizedValue);
	}

	onMount(() => {
		let cancelled = false;

		async function setup() {
			const { default: QuillEditor } = await import('quill');
			if (cancelled || !editorElement) return;
			const element = editorElement;

			QuillEditor.register({ 'formats/divider': DividerBlot });

			const editor = new QuillEditor(element, {
				theme: 'snow',
				placeholder,
				modules: { toolbar: TOOLBAR }
			});
			editor.root.setAttribute('role', 'textbox');
			editor.root.setAttribute('aria-multiline', 'true');
			if (label) editor.root.setAttribute('aria-label', label);

			applyValue(editor, value ?? '');
			quill = editor;

			// Registered after the stored value loads, so restoring existing
			// rich text never runs the markdown conversion.
			editor.clipboard.addMatcher(Node.TEXT_NODE, (node, delta: Delta) => {
				if (applyingExternalValue || !(node instanceof Text)) return delta;
				const text = node.data;
				if (!containsMarkdown(text)) return delta;
				return editor.clipboard.convert({ html: markdownToHtml(text) });
			});

			editor.on('text-change', () => {
				const html = readHtml(editor);
				lastEmitted = html;
				value = html;
			});
		}

		setup();

		return () => {
			cancelled = true;
			quill = null;
		};
	});

	/** Quill renders an empty document as `<p><br></p>`; store nothing instead. */
	function readHtml(editor: Quill): string {
		const html = editor.root.innerHTML;
		return /^<p>(<br\s*\/?>)?<\/p>$/i.test(html) ? '' : html;
	}

	function applyValue(editor: Quill, next: string) {
		// Rows saved before the editor existed hold plain text or markdown, whose
		// line breaks HTML would collapse, so they are rendered first.
		const html = looksLikeHtml(next) ? next : markdownToHtml(next);
		applyingExternalValue = true;
		try {
			editor.setContents(editor.clipboard.convert({ html }), 'silent');
			lastEmitted = next;
		} finally {
			applyingExternalValue = false;
		}
	}
</script>

<div class="rich-text-editor" class:rich-text-editor_compact={compact}>
	{#if label}
		<span class="editor-label">{label}</span>
	{/if}
	<div class="rich-text-editor__surface">
		<div bind:this={editorElement}></div>
	</div>
</div>
