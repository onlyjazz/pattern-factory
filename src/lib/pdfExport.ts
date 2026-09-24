/**
 * Browser-only helpers for exporting an OpenCRO risk report to PDF.
 *
 * Kept separate from the DOM-free report builders (riskReportPdf.ts) so the
 * document definitions stay testable outside the browser.
 */

// Rasterize the first <svg> inside the given element (e.g. a Google Chart) to a
// 2x PNG data URL so it can be embedded in the PDF.
export async function captureChartImage(elementId: string): Promise<string | null> {
	try {
		const chartEl = document.getElementById(elementId);
		const svg = chartEl?.querySelector('svg');
		if (!svg) return null;

		const rect = svg.getBoundingClientRect();
		const width = Math.round(rect.width) || svg.clientWidth || 800;
		const height = Math.round(rect.height) || svg.clientHeight || 500;
		const scale = 2;

		const clone = svg.cloneNode(true) as SVGSVGElement;
		clone.setAttribute('width', String(width));
		clone.setAttribute('height', String(height));
		clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');

		const serialized = new XMLSerializer().serializeToString(clone);
		const svgUrl = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(serialized)}`;

		const image = new Image();
		await new Promise<void>((resolve, reject) => {
			image.onload = () => resolve();
			image.onerror = () => reject(new Error('Chart image failed to load'));
			image.src = svgUrl;
		});

		const canvas = document.createElement('canvas');
		canvas.width = width * scale;
		canvas.height = height * scale;
		const ctx = canvas.getContext('2d');
		if (!ctx) return null;
		ctx.fillStyle = '#ffffff';
		ctx.fillRect(0, 0, canvas.width, canvas.height);
		ctx.drawImage(image, 0, 0, canvas.width, canvas.height);

		return canvas.toDataURL('image/png');
	} catch (e) {
		console.warn(`Could not capture chart "${elementId}" for PDF`, e);
		return null;
	}
}

// Inline an image as a data URL so pdfmake can embed it without a second request.
export async function loadImageAsDataUrl(url: string): Promise<string | null> {
	try {
		const response = await fetch(url);
		if (!response.ok) return null;
		const blob = await response.blob();
		return await new Promise<string | null>((resolve) => {
			const reader = new FileReader();
			reader.onloadend = () =>
				resolve(typeof reader.result === 'string' ? reader.result : null);
			reader.onerror = () => resolve(null);
			reader.readAsDataURL(blob);
		});
	} catch (e) {
		console.warn(`Could not load image "${url}" for PDF`, e);
		return null;
	}
}

// Generate and download a PDF. pdfmake is imported lazily so SvelteKit SSR is unaffected.
export async function downloadPdf(docDefinition: any, fileName: string): Promise<void> {
	const pdfMakeModule: any = await import('pdfmake/build/pdfmake');
	const pdfFontsModule: any = await import('pdfmake/build/vfs_fonts');
	const pdfMake = pdfMakeModule.default ?? pdfMakeModule;
	const pdfFonts = pdfFontsModule.default ?? pdfFontsModule;
	pdfMake.vfs = pdfFonts?.pdfMake?.vfs ?? pdfFonts?.vfs ?? pdfFonts;
	pdfMake.createPdf(docDefinition).download(fileName);
}
