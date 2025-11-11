<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { selectedStudy } from '$lib/selectedStudy';
  import DataTable from '$lib/DataTable.svelte';
  import { tableRegistry } from '$lib/stores/tableRegistry';
  
  interface ResultTable {
    rule_id: string;
    table_name: string;
    row_count: number;
    created_at: string;
  }
  
  let tables: ResultTable[] = [];
  let loading = false;
  let error = '';
  let selectedTable: ResultTable | null = null;
  let showModal = false;
  let tableData: any = null;
  let loadingData = false;
  let refreshInterval: NodeJS.Timeout;
  
  // Subscribe to study changes
  const unsubscribe = selectedStudy.subscribe(study => {
    if (study?.name) {
      fetchTables();
    }
  });
  
  onMount(() => {
    fetchTables();
    // Refresh every 30 seconds
    refreshInterval = setInterval(fetchTables, 30000);
  });
  
  onDestroy(() => {
    unsubscribe();
    if (refreshInterval) {
      clearInterval(refreshInterval);
    }
  });
  
  async function fetchTables() {
    const study = $selectedStudy;
    if (!study?.name) return;
    
    loading = true;
    error = '';
    
    try {
      const response = await fetch(`http://localhost:8000/api/results/${study.name}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch tables: ${response.statusText}`);
      }
      
      const data = await response.json();
      tables = data.tables || [];
      
      // Sort by created_at descending (newest first)
      tables.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    } catch (err) {
      console.error('Error fetching result tables:', err);
      error = err instanceof Error ? err.message : 'Failed to fetch tables';
      tables = [];
    } finally {
      loading = false;
    }
  }
  
  async function openTable(table: ResultTable) {
    const study = $selectedStudy;
    if (!study?.name) return;
    
    selectedTable = table;
    showModal = true;
    loadingData = true;
    tableData = null;
    
    try {
      const response = await fetch(`http://localhost:8000/api/results/${study.name}/${table.rule_id}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch table data: ${response.statusText}`);
      }
      
      tableData = await response.json();
      
      // Store data in tableRegistry for DataTable component
      const tableId = `results_${table.rule_id}_${Date.now()}`;
      if (tableData.data && tableData.data.length > 0) {
        tableRegistry.save(tableId, tableData.data);
        tableData.tableId = tableId;
      }
    } catch (err) {
      console.error('Error fetching table data:', err);
      error = err instanceof Error ? err.message : 'Failed to fetch table data';
    } finally {
      loadingData = false;
    }
  }
  
  function closeModal() {
    showModal = false;
    selectedTable = null;
    tableData = null;
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
    // Convert RULE_ID format to more readable format
    return ruleId.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  }
  
  function getSeverityClass(ruleId: string): string {
    // Determine severity based on rule ID patterns
    if (ruleId.includes('MISSING')) return 'severity-minor';
    if (ruleId.includes('HIGH') || ruleId.includes('LOW')) return 'severity-major';
    if (ruleId.includes('CRITICAL') || ruleId.includes('SEVERE')) return 'severity-critical';
    return 'severity-info';
  }
</script>

<div class="results-tables">
  <div class="header">
    <h3 class="title">
      <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
        <line x1="3" y1="9" x2="21" y2="9"></line>
        <line x1="9" y1="21" x2="9" y2="9"></line>
      </svg>
      Result Tables
    </h3>
    <button class="refresh-btn" on:click={fetchTables} disabled={loading} title="Refresh">
      <svg class="refresh-icon" class:spinning={loading} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="23 4 23 10 17 10"></polyline>
        <polyline points="1 20 1 14 7 14"></polyline>
        <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
      </svg>
    </button>
  </div>
  
  {#if error}
    <div class="error-message">
      <svg class="error-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
      </svg>
      {error}
    </div>
  {/if}
  
  {#if loading && tables.length === 0}
    <div class="loading">
      <div class="spinner"></div>
      Loading tables...
    </div>
  {:else if tables.length === 0}
    <div class="empty-state">
      <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M3 3h18v18H3zM3 9h18M9 21V9"></path>
      </svg>
      <p>No result tables available</p>
      <p class="hint">Run rules to generate result tables</p>
    </div>
  {:else}
    <div class="tables-list">
      {#each tables as table}
        <button 
          class="table-item {getSeverityClass(table.rule_id)}"
          on:click={() => openTable(table)}
          title="Click to view table data"
        >
          <div class="table-header">
            <span class="rule-id">{getRuleDisplay(table.rule_id)}</span>
            <span class="row-count" class:has-records={table.row_count > 0}>
              {table.row_count} {table.row_count === 1 ? 'record' : 'records'}
            </span>
          </div>
          <div class="table-meta">
            <span class="table-name">{table.table_name}</span>
            <span class="created-at">{formatDate(table.created_at)}</span>
          </div>
        </button>
      {/each}
    </div>
  {/if}
</div>

<!-- Modal for displaying table data -->
{#if showModal}
  <div class="modal-overlay" on:click={closeModal}>
    <div class="modal-content" on:click|stopPropagation>
      <div class="modal-header">
        <h2>{selectedTable ? getRuleDisplay(selectedTable.rule_id) : 'Table Data'}</h2>
        <button class="close-btn" on:click={closeModal}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      
      {#if selectedTable}
        <div class="modal-info">
          <span class="info-item">
            <strong>Table:</strong> {selectedTable.table_name}
          </span>
          <span class="info-item">
            <strong>Records:</strong> {selectedTable.row_count}
          </span>
          <span class="info-item">
            <strong>Created:</strong> {formatDate(selectedTable.created_at)}
          </span>
        </div>
      {/if}
      
      <div class="modal-body">
        {#if loadingData}
          <div class="loading">
            <div class="spinner"></div>
            Loading table data...
          </div>
        {:else if tableData && tableData.tableId}
          <DataTable 
            tableId={tableData.tableId}
            options={{
              pageLength: 25,
              lengthChange: true,
              ordering: true,
              searching: true,
              dom: 'Bfrtip',
              buttons: ['copy', 'csv', 'excel', 'pdf', 'print']
            }}
          />
        {:else if tableData && tableData.data && tableData.data.length === 0}
          <div class="empty-state">
            <p>No data in this table</p>
          </div>
        {:else}
          <div class="error-message">
            Failed to load table data
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .results-tables {
    height: 100%;
    display: flex;
    flex-direction: column;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  }
  
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    border-bottom: 1px solid #e0e0e0;
    background: #f8f9fa;
    border-radius: 8px 8px 0 0;
  }
  
  .title {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
    color: #333;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  
  .icon {
    width: 20px;
    height: 20px;
    color: #6c757d;
  }
  
  .refresh-btn {
    background: none;
    border: none;
    padding: 0.5rem;
    cursor: pointer;
    color: #6c757d;
    transition: all 0.2s;
    border-radius: 4px;
  }
  
  .refresh-btn:hover:not(:disabled) {
    background: #e9ecef;
    color: #495057;
  }
  
  .refresh-btn:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }
  
  .refresh-icon {
    width: 18px;
    height: 18px;
  }
  
  .refresh-icon.spinning {
    animation: spin 1s linear infinite;
  }
  
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
  
  .tables-list {
    flex: 1;
    overflow-y: auto;
    padding: 0.5rem;
  }
  
  .table-item {
    width: 100%;
    padding: 0.75rem;
    margin-bottom: 0.5rem;
    background: #fff;
    border: 1px solid #dee2e6;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
    text-align: left;
    position: relative;
    overflow: hidden;
  }
  
  .table-item::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 4px;
    background: currentColor;
  }
  
  .table-item.severity-critical::before {
    background: #dc3545;
  }
  
  .table-item.severity-major::before {
    background: #fd7e14;
  }
  
  .table-item.severity-minor::before {
    background: #ffc107;
  }
  
  .table-item.severity-info::before {
    background: #0dcaf0;
  }
  
  .table-item:hover {
    border-color: #0066cc;
    box-shadow: 0 2px 8px rgba(0, 102, 204, 0.15);
    transform: translateX(2px);
  }
  
  .table-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }
  
  .rule-id {
    font-weight: 600;
    color: #212529;
    font-size: 0.9rem;
  }
  
  .row-count {
    font-size: 0.8rem;
    padding: 0.2rem 0.5rem;
    background: #e9ecef;
    color: #6c757d;
    border-radius: 12px;
  }
  
  .row-count.has-records {
    background: #d1ecf1;
    color: #0c5460;
    font-weight: 500;
  }
  
  .table-meta {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    color: #6c757d;
  }
  
  .table-name {
    font-family: 'Courier New', monospace;
    background: #f8f9fa;
    padding: 0.1rem 0.3rem;
    border-radius: 3px;
  }
  
  .created-at {
    font-style: italic;
  }
  
  .loading, .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    color: #6c757d;
  }
  
  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid #f3f3f3;
    border-top: 3px solid #0066cc;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 1rem;
  }
  
  .empty-icon {
    width: 48px;
    height: 48px;
    color: #dee2e6;
    margin-bottom: 1rem;
  }
  
  .hint {
    font-size: 0.85rem;
    color: #adb5bd;
    margin-top: 0.25rem;
  }
  
  .error-message {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    background: #f8d7da;
    color: #721c24;
    border-radius: 4px;
    margin: 0.5rem;
    font-size: 0.9rem;
  }
  
  .error-icon {
    width: 20px;
    height: 20px;
    flex-shrink: 0;
  }
  
  /* Modal styles */
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    animation: fadeIn 0.2s;
  }
  
  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  
  .modal-content {
    background: white;
    border-radius: 12px;
    width: 90%;
    max-width: 1200px;
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
    animation: slideUp 0.3s;
  }
  
  @keyframes slideUp {
    from {
      transform: translateY(20px);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }
  
  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid #e0e0e0;
    background: #f8f9fa;
    border-radius: 12px 12px 0 0;
  }
  
  .modal-header h2 {
    margin: 0;
    font-size: 1.25rem;
    color: #212529;
  }
  
  .close-btn {
    background: none;
    border: none;
    padding: 0.5rem;
    cursor: pointer;
    color: #6c757d;
    transition: all 0.2s;
    border-radius: 4px;
  }
  
  .close-btn:hover {
    background: #e9ecef;
    color: #212529;
  }
  
  .close-btn svg {
    width: 20px;
    height: 20px;
  }
  
  .modal-info {
    display: flex;
    gap: 2rem;
    padding: 1rem 1.5rem;
    background: #f8f9fa;
    border-bottom: 1px solid #e0e0e0;
    font-size: 0.9rem;
  }
  
  .info-item strong {
    color: #495057;
    margin-right: 0.5rem;
  }
  
  .modal-body {
    flex: 1;
    overflow-y: auto;
    padding: 1.5rem;
  }
</style>
