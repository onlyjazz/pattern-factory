<script lang="ts">
    import { page } from '$app/stores';
    import { onMount, onDestroy } from 'svelte';
    import { selectedStudy } from '$lib/selectedStudy';
    import { selectedTable } from '$lib/stores/selectedTable';
    
    // Navigation items with Material Icons
    const navItems = [
      { href: '/studies', icon: 'dashboard', label: 'Studies' },
      { href: '/code', icon: 'swap_calls', label: 'Code' },
    ];
    
    interface ResultTable {
      rule_id: string;
      table_name: string;
      row_count: number;
      created_at: string;
    }
    
    let tables: ResultTable[] = [];
    let loading = false;
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
        tables = [];
      } finally {
        loading = false;
      }
    }
    
    function selectTable(table: ResultTable) {
      selectedTable.set(table);
      // Navigate to results page if not already there
      if ($page.url.pathname !== '/results') {
        window.location.href = '/results';
      }
    }
    
    function getRuleDisplay(ruleId: string): string {
      // Convert rule ID to title case for display
      return ruleId.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
</script>

<aside class="page-aside">
  <div class="main-nav">
    {#each navItems as item, i}
      <a href={item.href} class="main-nav__item {item.href === $page.url.pathname ? 'main-nav__item_active' : ''}">
        <span class="material-icons">{item.icon}</span>{item.label}
      </a>
      {#if i < navItems.length - 1}
        <hr class="main-nav__sep">
      {/if}
    {/each}
    
    <!-- Result Tables Section -->
    {#if $selectedStudy}
      <hr class="main-nav__sep">
      <div class="result-tables-section">
        <div class="section-header">
          <span class="material-icons">table_chart</span>
          <span>Result Tables</span>
          {#if loading}
            <span class="loading-spinner"></span>
          {/if}
        </div>
        
        {#if tables.length > 0}
          <div class="tables-list">
            {#each tables as table, i}
              <a
                href="/results"
                class="main-nav__item table-link {$selectedTable?.rule_id === table.rule_id ? 'main-nav__item_active' : ''}"
                onclick={(e) => { e.preventDefault(); selectTable(table); }}
                title="{getRuleDisplay(table.rule_id)} - {table.row_count} records"
              >
                {getRuleDisplay(table.rule_id)} ({table.row_count})
              </a>
              {#if i < tables.length - 1}
                <hr class="main-nav__sep">
              {/if}
            {/each}
          </div>
        {:else if !loading}
          <div class="no-tables">
            <span class="hint">No result tables</span>
          </div>
        {/if}
      </div>
    {/if}
  </div>
</aside>

<style>
    @import "../main.css";
    
    .material-icons {
        vertical-align: top;
        margin-right: 0.75rem;
    }
    
    .result-tables-section {
        padding: 0.5rem 0;
    }
    
    .section-header {
        display: flex;
        align-items: center;
        padding: 0.375rem 1rem;
        font-size: 0.75rem;
        font-weight: 600;
        color: #6c757d;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .section-header .material-icons {
        font-size: 18px;
        margin-right: 0.5rem;
    }
    
    .loading-spinner {
        margin-left: auto;
        width: 12px;
        height: 12px;
        border: 2px solid #f3f3f3;
        border-top: 2px solid #0066cc;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    
    .tables-list {
        max-height: 500px;  /* Increased height since items are smaller */
        overflow-y: auto;
    }
    
    /* Use smaller styling for table links to fit more items */
    .tables-list .main-nav__item {
        font-size: 0.8rem;
        padding: 0.375rem 1rem;
        padding-left: 1.5rem;  /* Indent slightly since no icon */
        line-height: 1.3;
    }
    
    /* Make separators thinner in tables list */
    .tables-list .main-nav__sep {
        margin: 0.125rem 0;
    }
    
    .table-link.active {
        background: #e7f3ff;
        color: #0066cc;
        font-weight: 500;
    }
    
    .table-name {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        text-transform: capitalize;
    }
    
    .table-count {
        margin-left: 0.5rem;
        padding: 0.125rem 0.375rem;
        background: #e9ecef;
        border-radius: 10px;
        font-size: 0.75rem;
        color: #6c757d;
    }
    
    .table-link.active .table-count {
        background: #0066cc;
        color: white;
    }
    
    .no-tables {
        padding: 1rem;
        text-align: center;
    }
    
    .hint {
        font-size: 0.8rem;
        color: #adb5bd;
        font-style: italic;
    }
    
    /* Scrollbar styling for tables list */
    .tables-list::-webkit-scrollbar {
        width: 6px;
    }
    
    .tables-list::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 3px;
    }
    
    .tables-list::-webkit-scrollbar-thumb {
        background: #888;
        border-radius: 3px;
    }
    
    .tables-list::-webkit-scrollbar-thumb:hover {
        background: #555;
    }
</style>
