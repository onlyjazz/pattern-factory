<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import { tableRegistry } from '$lib/stores/tableRegistry';
    import 'datatables.net-dt/css/dataTables.dataTables.css';
    import 'datatables.net-buttons-dt/css/buttons.dataTables.css';
  
    export let tableId: string;                 // unique per message
    export let options: Record<string, any> = {}; // DataTables options
  
    let tableEl: HTMLTableElement;
    let dt: any;
  
    // Load rows once from the registry; this table is "owned" by tableId
    const rows = tableRegistry.get(tableId) ?? [];
  
    const headers = () => (rows?.length ? Object.keys(rows[0]) : []);
  
    onMount(async () => {
      // Import required libraries for export functionality first
      // @ts-ignore
      window.JSZip = (await import('jszip')).default;
      // @ts-ignore
      const pdfMake = await import('pdfmake/build/pdfmake');
      // @ts-ignore
      const pdfFonts = await import('pdfmake/build/vfs_fonts');
      // @ts-ignore
      if (pdfMake && pdfMake.vfs) {
        pdfMake.vfs = pdfFonts.vfs || pdfFonts.default.vfs;
      }
      
      // Import DataTable and extensions
      const DataTable = (await import('datatables.net')).default;
      const Buttons = (await import('datatables.net-buttons')).default;
      
      // Import button types
      await import('datatables.net-buttons/js/buttons.html5.js');
      await import('datatables.net-buttons/js/buttons.print.js');
      await import('datatables.net-buttons/js/buttons.colVis.js');
      
      // Register Buttons with DataTable if needed
      if (!DataTable.Buttons) {
        DataTable.Buttons = Buttons;
      }
  
      // map objects -> row arrays in header order
      const data = rows.map((r) => headers().map((h) => r?.[h]));
  
      dt = new DataTable(tableEl, {
        data,
        columns: headers().map((h) => ({ title: h })),
        paging: true,
        searching: true,
        ordering: true,
        responsive: true,
        ...options
      });
    });
  
    // This table is immutable: it won’t react to later global registry changes.
    // If you need a "refresh" button for THIS tableId, expose a method to re-pull.
  
    onDestroy(() => {
      dt?.destroy?.();
      dt = null;
    });
  </script>
  
  <table bind:this={tableEl} class="display w-full"></table>
  
  <style>
    /* Import DataTables CSS */
    @import 'datatables.net-dt/css/dataTables.dataTables.css';
    @import 'datatables.net-buttons-dt/css/buttons.dataTables.css';
  </style>
  