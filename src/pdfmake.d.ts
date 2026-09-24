// pdfmake ships untyped UMD builds. Declare the specific entry points we
// import so svelte-check resolves the dynamic imports in the model-risk page.
declare module 'pdfmake/build/pdfmake' {
	const pdfMake: any;
	export default pdfMake;
}

declare module 'pdfmake/build/vfs_fonts' {
	const vfsFonts: any;
	export default vfsFonts;
}
