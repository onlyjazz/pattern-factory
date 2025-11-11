<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { selectedStudy } from '$lib/selectedStudy';
  import { selectedTable } from '$lib/stores/selectedTable';
  import DataTable from '$lib/DataTable.svelte';
  import { tableRegistry } from '$lib/stores/tableRegistry';
  
  let tableData: any = null;
  let loading = false;
  let error = '';
  
  // Subscribe to selected table changes
  const unsubscribe = selectedTable.subscribe(table => {
    if (table) {
      loadTableData(table);
    }
  });
  
  onDestroy(() => {
    unsubscribe();
  });
  
  async function loadTableData(table: any) {
    const study = $selectedStudy;
    if (!study?.name || !table) return;
    
    loading = true;
    error = '';
    tableData = null;
    
    try {
      const response = await fetch(`http://localhost:8000/api/results/${study.name}/${table.rule_id}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch table data: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      // Store data in tableRegistry for DataTable component
      const tableId = `results_${table.rule_id}_${Date.now()}`;
      if (data.data && data.data.length > 0) {
        tableRegistry.save(tableId, data.data);
        tableData = {
          ...data,
          tableId,
          table
        };
      } else {
        tableData = {
          ...data,
          table,
          empty: true
        };
      }
    } catch (err) {
      console.error('Error fetching table data:', err);
      error = err instanceof Error ? err.message : 'Failed to fetch table data';
    } finally {
      loading = false;
    }
  }
  
  function formatDate(dateStr: string): string {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateStr;
    }
  }
  
  function getRuleDisplay(ruleId: string): string {
    return ruleId.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  }
</script>

{#if $selectedTable}
  <div class="page-title">
    <h1 class="heading heading_1">{getRuleDisplay($selectedTable.rule_id)}</h1>
  </div>

  <div class="grid-row">
    <div class="grid-col grid-col_24">
      <div class="results card">
        <div class="table">
          {#if loading}
            <div class="loading-state">
              <div class="spinner"></div>
              <p>Loading table data...</p>
            </div>
          {:else if error}
            <div class="error-state">
              <span class="material-icons">error_outline</span>
              <h3>Error Loading Data</h3>
              <p>{error}</p>
              <button class="button button_green" onclick={() => loadTableData($selectedTable)}>
                Try Again
              </button>
            </div>
          {:else if tableData?.empty}
            <div class="empty-state">
              <span class="material-icons">inbox</span>
              <h3>No Data Available</h3>
              <p>This table contains no records.</p>
            </div>
          {:else if tableData?.tableId}
            <DataTable 
              tableId={tableData.tableId}
              options={{
                pageLength: 10000,
                lengthChange: false,
                paging: false,
                ordering: true,
                searching: true,
                dom: '<"row"<"col-sm-6"B><"col-sm-6"f>>rtip',
                buttons: [
                  {
                    extend: 'csv',
                    text: '<span class="material-icons">download</span> CSV',
                    className: 'btn-export-csv',
                    title: 'Export to CSV',
                    filename: function() {
                      const study = $selectedStudy?.name || 'study';
                      const table = $selectedTable?.rule_id || 'data';
                      const date = new Date().toISOString().split('T')[0];
                      return `${study}_${table}_${date}`;
                    }
                  }
                ],
                responsive: true,
                autoWidth: false,
                deferRender: true
              }}
            />
          {/if}
        </div>
      </div>
    </div>
  </div>
{:else}
  <div class="no-selection-state">
    <span class="material-icons">table_chart</span>
    <h2>No Table Selected</h2>
    <p>Select a result table from the sidebar to view its data.</p>
    {#if !$selectedStudy}
      <p class="hint">First, select a study from the Studies page.</p>
      <a href="/studies" class="button button_green">Go to Studies</a>
    {/if}
  </div>
{/if}

<style>
  .loading-state,
  .error-state,
  .empty-state,
  .no-selection-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 400px;
    text-align: center;
    color: #6c757d;
  }
  
  .loading-state .spinner {
    width: 48px;
    height: 48px;
    border: 4px solid #f3f3f3;
    border-top: 4px solid #0066cc;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 1rem;
  }
  
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
  
  .error-state .material-icons,
  .empty-state .material-icons,
  .no-selection-state .material-icons {
    font-size: 64px;
    color: #dee2e6;
    margin-bottom: 1rem;
  }
  
  .error-state .material-icons {
    color: #dc3545;
  }
  
  .error-state h3,
  .empty-state h3,
  .no-selection-state h2 {
    margin: 0 0 0.5rem 0;
    color: #495057;
  }
  
  .error-state p,
  .empty-state p,
  .no-selection-state p {
    margin: 0 0 1.5rem 0;
    color: #6c757d;
  }
  
  .hint {
    font-size: 0.9rem;
    color: #adb5bd;
    font-style: italic;
  }
  
  /* Style DataTable search box - target all possible selectors */
  :global(.dataTables_filter input[type="search"]),
  :global(.dataTables_filter input),
  :global(.dataTables_wrapper input[type="search"]),
  :global(input[type="search"]),
  :global(.dt-search input),
  :global(.dt-input) {
    border: 1px solid #dee2e6 !important;
    border-radius: 4px !important;
    padding: 0.375rem 0.75rem !important;
    font-size: 0.875rem !important;
    transition: border-color 0.15s ease-in-out !important;
    background-color: white !important;
    box-sizing: border-box !important;
  }
  
  :global(.dataTables_filter input[type="search"]:focus),
  :global(.dataTables_filter input:focus),
  :global(.dataTables_wrapper input[type="search"]:focus),
  :global(input[type="search"]:focus),
  :global(.dt-search input:focus),
  :global(.dt-input:focus) {
    outline: none !important;
    border-color: #80bdff !important;
    box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25) !important;
  }
  
  /* Add padding to the DataTable wrapper */
  :global(.dataTables_wrapper),
  :global(.dt-container) {
    padding: 1rem 0;
  }
  
  /* Also target the search container itself */
  :global(.dataTables_filter),
  :global(.dt-search) {
    margin-bottom: 0;
  }
  
  /* Hide the "Search:" label text */
  :global(.dataTables_filter label),
  :global(.dt-search label) {
    font-size: 0;
  }
  
  /* Keep the input visible */
  :global(.dataTables_filter label input),
  :global(.dt-search label input) {
    font-size: 0.875rem !important;
  }
  
  /* Style DataTables export buttons */
  :global(.dt-buttons),
  :global(.dataTables_wrapper .dt-buttons) {
    display: inline-block !important;
    visibility: visible !important;
    opacity: 1 !important;
    position: relative !important;
    z-index: 10 !important;
  }
  
  :global(.dt-button),
  :global(.dt-buttons button),
  :global(.dt-buttons .dt-button),
  :global(button.dt-button) {
    background: white !important;
    border: 1px solid #dee2e6 !important;
    border-radius: 4px !important;
    padding: 0.375rem 0.75rem !important;
    margin: 0 0.25rem !important;
    font-size: 0.875rem !important;
    font-family: 'Roboto', system-ui, -apple-system, sans-serif !important;
    color: #495057 !important;
    cursor: pointer !important;
    transition: all 0.2s !important;
    display: inline-flex !important;
    align-items: center !important;
    gap: 0.375rem !important;
    line-height: 1.5 !important;
  }
  
  :global(.dt-button:hover),
  :global(.dt-buttons button:hover) {
    background: #e9ecef !important;
    border-color: #adb5bd !important;
    color: #212529 !important;
  }
  
  :global(.dt-button:active),
  :global(.dt-buttons button:active) {
    background: #dee2e6 !important;
    transform: translateY(1px);
  }
  
  /* Highlight CSV button - force green color */
  :global(.btn-export-csv),
  :global(.dt-button.btn-export-csv),
  :global(.dt-buttons .btn-export-csv),
  :global(button.btn-export-csv) {
    background: #28a745 !important;
    background-color: #28a745 !important;
    border-color: #28a745 !important;
    color: white !important;
  }
  
  :global(.btn-export-csv:hover),
  :global(.dt-button.btn-export-csv:hover),
  :global(button.btn-export-csv:hover) {
    background: #218838 !important;
    background-color: #218838 !important;
    border-color: #1e7e34 !important;
    color: white !important;
  }
  
  /* Style the material icons in buttons */
  :global(.dt-button .material-icons),
  :global(.dt-buttons .material-icons) {
    font-size: 18px !important;
    vertical-align: middle !important;
  }
  
  /* Force DataTables v2 layout to be horizontal */
  :global(.dt-container .dt-layout-row:first-child),
  :global(.dt-layout-row:has(.dt-buttons)) {
    display: flex !important;
    justify-content: space-between !important;
    align-items: center !important;
    margin-bottom: 1rem !important;
    width: 100% !important;
  }
  
  /* Make cells flex items */
  :global(.dt-layout-cell) {
    display: flex !important;
    align-items: center !important;
    visibility: visible !important;
  }
  
  /* Position buttons on the left of top row */
  :global(.dt-layout-start:first-child) {
    flex: 1 1 auto !important;
    justify-content: flex-start !important;
  }
  
  /* Position search on the right of top row */
  :global(.dt-layout-end:first-child) {
    flex: 0 0 auto !important;
    justify-content: flex-end !important;
  }
  
  /* Ensure buttons container stays inline */
  :global(.dt-buttons) {
    display: inline-block !important;
    margin: 0 !important;
  }
  
  :global(.dt-search) {
    display: inline-block !important;
    margin: 0 !important;
  }
  
  /* Contain horizontal scroll within the card */
  :global(.results.card) {
    overflow: hidden;
  }
  
  :global(.results.card .table) {
    overflow-x: auto;
    overflow-y: visible;
    width: 100%;
    max-width: 100%;
  }
  
  /* Only make the actual table scrollable, not the wrapper */
  :global(.dataTables_wrapper) {
    width: 100%;
    overflow: hidden !important;
  }
  
  :global(.dataTables_scrollBody),
  :global(.dataTables_scroll .dataTables_scrollBody) {
    overflow-x: auto !important;
    overflow-y: visible !important;
  }
  
  /* Make just the table container scrollable */
  :global(.dataTables_wrapper table),
  :global(.dataTables_wrapper .dataTables_scrollBody table) {
    width: 100% !important;
  }
  
  :global(.dataTables_wrapper .dataTables_scroll) {
    overflow-x: auto !important;
    margin-bottom: 0.5rem !important;
  }
  
  :global(.dataTables_scroll) {
    overflow-x: auto;
  }
  
  :global(.dataTables_scrollBody) {
    overflow-x: auto !important;
  }
  
  /* Ensure table doesn't force card to expand */
  :global(table.dataTable),
  :global(table.display) {
    width: 100% !important;
    min-width: 600px !important; /* Minimum width to prevent cramping */
  }
  
  /* DataTables v2 specific - Create horizontal layout for info and pagination */
  :global(.dt-container) {
    width: 100% !important;
    overflow-x: auto !important;
  }
  
  /* Info text styling - DataTables v2 */
  :global(.dt-info) {
    font-size: 0.875rem !important;
    color: #495057 !important;
    font-family: 'Roboto', system-ui, -apple-system, sans-serif !important;
    font-weight: 400 !important;
    margin-top: 1.5rem !important;
    padding-top: 1rem !important;
    border-top: 1px solid #dee2e6 !important;
    display: inline-block !important;
    width: 49% !important;
    text-align: left !important;
  }
  
  /* Pagination container - DataTables v2 */
  :global(.dt-paging) {
    display: inline-block !important;
    width: 49% !important;
    text-align: right !important;
    margin-top: 1.5rem !important;
    padding-top: 1rem !important;
    border-top: 1px solid #dee2e6 !important;
    vertical-align: top !important;
  }
  
  /* Ensure nav is inline */
  :global(.dt-paging nav) {
    display: inline-block !important;
    white-space: nowrap !important;
  }
  
  /* Style pagination buttons - DataTables v2 */
  :global(.dt-paging-button),
  :global(button.dt-paging-button) {
    display: inline-block !important;
    padding: 0.375rem 0.75rem !important;
    margin: 0 0.125rem !important;
    border: 1px solid #dee2e6 !important;
    border-radius: 4px !important;
    background: white !important;
    color: #495057 !important;
    font-size: 0.875rem !important;
    font-family: 'Roboto', system-ui, -apple-system, sans-serif !important;
    line-height: 1.5 !important;
    cursor: pointer;
    transition: all 0.2s !important;
    min-width: 2.5rem !important;
    text-align: center !important;
    vertical-align: middle !important;
    white-space: nowrap !important;
  }
  
  :global(.dt-paging-button:hover:not(.disabled)) {
    background: #e9ecef !important;
    border-color: #adb5bd !important;
    color: #212529 !important;
  }
  
  :global(.dt-paging-button.current) {
    background: #0066cc !important;
    border-color: #0066cc !important;
    color: white !important;
  }
  
  :global(.dt-paging-button.disabled) {
    opacity: 0.5 !important;
    cursor: not-allowed !important;
    background: #f8f9fa !important;
  }
  
  /* First/Last/Previous/Next button styling */
  :global(.dt-paging-button.first),
  :global(.dt-paging-button.last),
  :global(.dt-paging-button.previous),
  :global(.dt-paging-button.next) {
    font-weight: 500 !important;
    min-width: auto !important;
    padding: 0.375rem 1rem !important;
  }
  
  /* Ensure pagination wrapper is wide enough */
  :global(.paging_simple_numbers),
  :global(.paging_full_numbers) {
    display: inline-block !important;
    width: auto !important;
    white-space: nowrap !important;
  }
  
  /* Setup Bootstrap-style row layout for DataTables */
  :global(.dataTables_wrapper .row) {
    display: flex !important;
    width: 100% !important;
    margin: 0 !important;
    align-items: center !important;
  }
  
  :global(.dataTables_wrapper .row:first-child) {
    margin-bottom: 1rem !important;
  }
  
  :global(.dataTables_wrapper .col-sm-6) {
    width: 50% !important;
    display: inline-block !important;
    padding: 0 !important;
  }
  
  :global(.dataTables_wrapper .col-sm-6:first-child) {
    text-align: left !important;
  }
  
  :global(.dataTables_wrapper .col-sm-6:last-child) {
    text-align: right !important;
  }
  
  /* Override for other column sizes if they exist */
  :global(.dataTables_wrapper .col-sm-12),
  :global(.dataTables_wrapper .col-md-5),
  :global(.dataTables_wrapper .col-md-7) {
    width: auto !important;
    flex: 1 !important;
    display: inline-block !important;
  }
  
  /* Force horizontal layout for bottom row */
  :global(.dataTables_wrapper .row:has(.dataTables_info)),
  :global(.dataTables_wrapper .row:has(.dataTables_paginate)) {
    display: flex !important;
    flex-direction: row !important;
    justify-content: space-between !important;
    align-items: center !important;
    width: 100% !important;
  }
  
  /* Ensure info and paginate are side by side */
  :global(.dataTables_wrapper .col-sm-12.col-md-5),
  :global(.dataTables_wrapper .col-sm-5) {
    width: auto !important;
    flex: 0 0 auto !important;
    display: inline-block !important;
  }
  
  :global(.dataTables_wrapper .col-sm-12.col-md-7),
  :global(.dataTables_wrapper .col-sm-7) {
    width: auto !important;
    flex: 0 0 auto !important;
    display: inline-block !important;
    text-align: right !important;
  }
  
  :global(.dataTables_length) {
    margin-bottom: 1rem !important;
  }
  
  :global(.dataTables_length label),
  :global(.dataTables_length select) {
    font-size: 0.875rem !important;
    color: #495057 !important;
    font-family: 'Roboto', system-ui, -apple-system, sans-serif !important;
  }
  
  :global(.dataTables_length select) {
    border: 1px solid #dee2e6 !important;
    border-radius: 4px !important;
    padding: 0.25rem 0.5rem !important;
    margin: 0 0.5rem !important;
  }
  
  /* Style all pagination links - use more specific selectors */
  :global(.paginate_button),
  :global(.paginate_button.current),
  :global(.paginate_button.disabled),
  :global(a.paginate_button),
  :global(span.paginate_button),
  :global(.pagination .paginate_button),
  :global(.dataTables_paginate .paginate_button),
  :global(.dataTables_paginate a),
  :global(.dataTables_paginate span) {
    display: inline-block !important;
    padding: 0.375rem 0.75rem !important;
    margin: 0 0.125rem !important;
    border: 1px solid #dee2e6 !important;
    border-radius: 4px !important;
    background: white !important;
    color: #495057 !important;
    font-size: 0.875rem !important;
    font-family: 'Roboto', system-ui, -apple-system, sans-serif !important;
    line-height: 1.5 !important;
    text-decoration: none !important;
    cursor: pointer;
    transition: all 0.2s !important;
    min-width: 2.5rem !important;
    text-align: center !important;
  }
  
  :global(.paginate_button:hover:not(.disabled)),
  :global(a.paginate_button:hover:not(.disabled)),
  :global(.dataTables_paginate a:hover:not(.disabled)) {
    background: #e9ecef !important;
    border-color: #adb5bd !important;
    color: #212529 !important;
    text-decoration: none !important;
  }
  
  :global(.paginate_button.current),
  :global(span.paginate_button.current),
  :global(.dataTables_paginate .current) {
    background: #0066cc !important;
    border-color: #0066cc !important;
    color: white !important;
  }
  
  :global(.paginate_button.disabled),
  :global(span.paginate_button.disabled),
  :global(.dataTables_paginate .disabled) {
    opacity: 0.5 !important;
    cursor: not-allowed !important;
    background: #f8f9fa !important;
  }
  
  /* Previous/Next/First/Last button styling */
  :global(.paginate_button.previous),
  :global(.paginate_button.next),
  :global(.paginate_button.first),
  :global(.paginate_button.last),
  :global(a.previous),
  :global(a.next),
  :global(a.first),
  :global(a.last) {
    font-weight: 500 !important;
    min-width: auto !important;
    padding: 0.375rem 1rem !important;
  }
  
  /* Ellipsis styling */
  :global(.paginate_button.ellipsis),
  :global(span.ellipsis) {
    border: none !important;
    background: transparent !important;
    cursor: default !important;
    padding: 0.375rem 0.25rem !important;
  }
  
  /* Give the bottom area more breathing room and ensure full width */
  :global(.dataTables_wrapper .row:last-child),
  :global(.dataTables_wrapper > div:last-child),
  :global(.dataTables_wrapper .bottom) {
    margin-bottom: 1rem !important;
    width: 100% !important;
    overflow: visible !important;
  }
  
  /* Ensure pagination container has enough width */
  :global(.dataTables_wrapper) {
    width: 100% !important;
    overflow: visible !important;
  }
  
  /* Clear floats after pagination */
  :global(.dataTables_wrapper::after) {
    content: "" !important;
    display: table !important;
    clear: both !important;
  }
  
  /* Style the table borders to match studies page */
  :global(.dataTable thead th),
  :global(.dt-table thead th),
  :global(table.display thead th) {
    border-bottom: 2px solid #dee2e6 !important;
  }
  
  :global(.dataTable tbody tr),
  :global(.dt-table tbody tr),
  :global(table.display tbody tr) {
    border-bottom: 1px solid #dee2e6 !important;
  }
  
  /* Remove default DataTable borders */
  :global(table.dataTable),
  :global(table.dt-table),
  :global(table.display) {
    border-collapse: collapse !important;
  }
  
  :global(table.dataTable td),
  :global(table.dataTable th),
  :global(table.dt-table td),
  :global(table.dt-table th),
  :global(table.display td),
  :global(table.display th) {
    border: none !important;
  }
</style>
