<script lang="ts">
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { globalSearch } from '$lib/searchStore';
  import ExportCSV from '$lib/ExportCSV.svelte';
  
  let viewName = '';
  let viewTitle = 'Views';
  let viewSummary = '';
  let data: any[] = [];
  let columns: string[] = [];
  let loading = true;
  let error = '';
  let filteredData: any[] = [];
  let sortColumn: string | null = null;
  let sortDirection: 'asc' | 'desc' = 'asc';
  const apiBase = 'http://localhost:8000';
  
  $: filteredData = updateFilteredData(data, $globalSearch, sortColumn, sortDirection);
  
  function updateFilteredData(data: any[], search: string, col: string | null, dir: 'asc' | 'desc'): any[] {
    let result = data;
    
    // Apply search filter
    if (search.trim() !== '') {
      const term = search.toLowerCase();
      result = result.filter(row =>
        Object.values(row).some(val =>
          String(val).toLowerCase().includes(term)
        )
      );
    }
    
    // Apply sorting
    if (col) {
      result = [...result].sort((a, b) => {
        const aVal = a[col];
        const bVal = b[col];
        
        // Handle null/undefined
        if (aVal == null && bVal == null) return 0;
        if (aVal == null) return dir === 'asc' ? 1 : -1;
        if (bVal == null) return dir === 'asc' ? -1 : 1;
        
        // Compare values
        if (typeof aVal === 'string' && typeof bVal === 'string') {
          return dir === 'asc'
            ? aVal.localeCompare(bVal)
            : bVal.localeCompare(aVal);
        }
        
        // Numeric or other comparison
        if (aVal < bVal) return dir === 'asc' ? -1 : 1;
        if (aVal > bVal) return dir === 'asc' ? 1 : -1;
        return 0;
      });
    }
    
    return result;
  }
  
  function handleColumnSort(col: string) {
    if (sortColumn === col) {
      // Toggle direction if clicking same column
      sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      // New column, default to ascending
      sortColumn = col;
      sortDirection = 'asc';
    }
  }
  
  function getSortIndicator(col: string): string {
    if (sortColumn !== col) return '';
    return sortDirection === 'asc' ? ' ▲' : ' ▼';
  }

  async function loadViewData(view: string) {
    if (!view) {
      error = 'No view specified';
      loading = false;
      return;
    }
    
    loading = true;
    error = '';
    data = [];
    columns = [];
    viewSummary = '';
    sortColumn = null;
    sortDirection = 'asc';
    
    try {
      // Fetch view metadata from views_registry
      const registryResponse = await fetch(`${apiBase}/query/views_registry`);
      if (registryResponse.ok) {
        const registryData = await registryResponse.json();
        const viewEntry = registryData.find((v: any) => v.table_name === view);
        if (viewEntry) {
          viewTitle = viewEntry.name || getDisplayName();
          viewSummary = viewEntry.summary || '';
        } else {
          viewTitle = getDisplayName();
        }
      } else {
        viewTitle = getDisplayName();
      }
      
      // Fetch view data
      const response = await fetch(`${apiBase}/query/${view}`);
      if (!response.ok) throw new Error('Failed to fetch view data');
      data = await response.json();
      
      // Extract column names from first row
      if (data.length > 0) {
        columns = Object.keys(data[0]);
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Unknown error';
    } finally {
      loading = false;
    }
  }
  
  onMount(() => {
    const unsubscribe = page.subscribe(($page) => {
      const newView = $page.url.searchParams.get('view') || '';
      if (newView && newView !== viewName) {
        viewName = newView;
        loadViewData(newView);
      }
    });
    
    // Initial load
    viewName = $page.url.searchParams.get('view') || '';
    loadViewData(viewName);

    return () => unsubscribe();
  });
  
  function formatValue(value: any): string {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'string' && value.startsWith('http')) {
      return value;
    }
    
    // Check if value looks like an ISO timestamp (YYYY-MM-DDTHH:mm:ss or similar)
    if (typeof value === 'string') {
      const datePattern = /^\d{4}-\d{2}-\d{2}(T|\s)/;
      if (datePattern.test(value)) {
        try {
          const date = new Date(value);
          // Check if date is valid
          if (!isNaN(date.getTime())) {
            // Format as "Mon Day, Year" (e.g., "Dec 3, 2025")
            return date.toLocaleDateString('en-US', {
              year: 'numeric',
              month: 'short',
              day: 'numeric'
            });
          }
        } catch (e) {
          // If parsing fails, fall through to default
        }
      }
    }
    
    return String(value);
  }

  function isUrl(value: any): boolean {
    return typeof value === 'string' && value.startsWith('http');
  }

  function isHtmlLink(value: any): boolean {
    return typeof value === 'string' && /<a\s+href=/.test(value);
  }

  function addTargetBlank(html: string): string {
    return html.replace(/<a\s+href=/gi, '<a target="_blank" rel="noopener noreferrer" href=');
  }

  // Convert view name to display name
  function getDisplayName(): string {
    const names: Record<string, string> = {
      pattern_episodes: 'Patterns in Episodes',
      pattern_guests: 'Patterns by Guest',
      pattern_orgs: 'Patterns by Organization',
      pattern_posts: 'Patterns by Post'
    };
    return names[viewName] || viewName;
  }
  
  // Format column names from snake_case to Title Case
  function formatColumnName(col: string): string {
    return col
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }
</script>

<div id="application-content-area">
  <div class="page-title">
    <h1 class="heading heading_1">{viewTitle}</h1>
  </div>

  <div class="grid-row">
    <!-- RIGHT TABLE (FULL WIDTH) -->
    <div class="grid-col grid-col_24">
      <div class="studies card">
        <div class="heading heading_3">{viewSummary || getDisplayName()}</div>

        {#if loading}
          <div class="message">Loading data...</div>
        {:else if error}
          <div class="message message-error">Error: {error}</div>
        {:else if data.length === 0}
          <div class="message">No data found</div>
        {:else}
          <div class="results-info">
            <ExportCSV {data} fileName="{viewName || 'export'}.csv" />
            <span class="search-results">{filteredData.length} of {data.length} results</span>
          </div>
          
          <div class="table">
            <table>
              <thead>
                <tr>
                  {#each columns as col}
                    <th
                      class="tal sortable"
                      on:click={() => handleColumnSort(col)}
                      aria-sort={sortColumn === col ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}
                    >
                      {formatColumnName(col)}
                      <span class="sort-indicator" aria-hidden="true">{getSortIndicator(col)}</span>
                    </th>
                  {/each}
                </tr>
              </thead>
              <tbody>
                {#each filteredData as row, idx}
                  <tr class={idx % 2 === 0 ? 'stripe1' : 'stripe2'}>
                    {#each columns as col}
                      <td class="tal">
                        {#if isHtmlLink(row[col])}
                          {@html addTargetBlank(row[col])}
                        {:else if isUrl(row[col])}
                          <a href={row[col]} target="_blank" rel="noopener noreferrer" class="text-link text-link_blue">
                            {row[col].substring(0, 50)}...
                          </a>
                        {:else}
                          {formatValue(row[col])}
                        {/if}
                      </td>
                    {/each}
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    </div>
  </div>
</div>

<style>
  :global(td a) {
    color: #0066cc;
    text-decoration: underline;
  }

  :global(td a:hover) {
    color: #0052a3;
  }

  .results-info {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
  }
  
  .search-results {
    font-size: 0.875rem;
    color: #6c757d;
    white-space: nowrap;
  }
  
  :global(th.sortable) {
    cursor: pointer !important;
    user-select: none !important;
    transition: background-color 0.2s ease !important;
  }
  
  :global(th.sortable:hover) {
    background-color: #f5f5f5 !important;
  }
  
  /* Explicit sort indicator styling to ensure visibility */
  th.sortable .sort-indicator {
    display: inline-block;
    margin-left: 6px;
    color: #6c757d;
    font-size: 0.85em;
    line-height: 1;
    vertical-align: middle;
  }
  
  /* Alternating row colors */
  :global(tr.stripe1),
  :global(tbody tr.stripe1) {
    background-color: #ffffff !important;
  }
  
  :global(tr.stripe2),
  :global(tbody tr.stripe2) {
    background-color: #f8f9fa !important;
  }
  
  /* Hover effect on rows */
  :global(tbody tr:hover) {
    background-color: #e8f0f7 !important;
  }
</style>
