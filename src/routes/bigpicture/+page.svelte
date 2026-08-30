<script lang="ts">
  import { onMount } from 'svelte';
import { API_BASE } from '$lib/config';
  
  let chartThreats: any[] = [];
  let allThreats: any[] = [];
  let loading = true;
  let error = '';
  let chartInitialized = false;
  const apiBase = API_BASE;
  
  function formatNumber(num: number): string {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1) + 'M';
    }
    if (num >= 1000) {
      return (num / 1000).toFixed(0) + 'K';
    }
    return num.toString();
  }
  
  function drawChart() {
    if (!chartThreats.length) return;
    
    const container = document.getElementById('curve_chart');
    if (!container) return;
    
    const data = google.visualization.arrayToDataTable([
      ['Threat', 'VaR Before Mitigation', 'VaR After Mitigation'],
      ...chartThreats.map(t => [t.threat_tag, t.var_before_mitigation, t.var_after_mitigation])
    ]);
    
    const options = {
      title: '',
      legend: { position: 'bottom', textStyle: { fontSize: 13 } },
      hAxis: {
        title: 'Threats',
        titleTextStyle: { color: '#333', fontSize: 13 },
        textStyle: { fontSize: 13, color: '#666' }
      },
      vAxis: {
        title: 'Value (VaR)',
        titleTextStyle: { color: '#333', fontSize: 13 },
        textStyle: { fontSize: 13, color: '#666' },
        format: '#,###'
      },
      colors: ['#2563eb', '#16a34a'],
      chartArea: { width: '75%', height: '75%' },
      bar: { groupWidth: '75%' },
      tooltip: { textStyle: { fontSize: 12, color: '#333' } },
      fontName: 'Roboto'
    };
    
    const chart = new google.visualization.ColumnChart(container);
    chart.draw(data, options);
  }
  
  onMount(async () => {
    try {
      // First, try to fetch chart data from THRIM
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);
      
      const response = await fetch(`${apiBase}/query/THRIM`, { signal: controller.signal });
      clearTimeout(timeoutId);
      
      if (response.ok) {
        const allData = await response.json();
        
        // Filter out rows with all null threat values, keep only rows with actual threat data
        const validThreats = allData.filter((t: any) => 
          t.var_before_mitigation !== null && t.var_before_mitigation !== undefined
        );
        
        // Get top 5 rows with valid data for chart
        chartThreats = validThreats.slice(0, 5);
        
        // Only load Google Charts if we have valid threat data
        if (chartThreats.length > 0) {
          // Load Google Charts library after DOM is ready
          if (!window.google) {
            const script = document.createElement('script');
            script.src = 'https://www.gstatic.com/charts/loader.js';
            script.onload = () => {
              google.charts.load('current', { packages: ['corechart'] });
              google.charts.setOnLoadCallback(() => {
                drawChart();
              });
            };
            document.head.appendChild(script);
          } else {
            google.charts.load('current', { packages: ['corechart'] });
            google.charts.setOnLoadCallback(() => {
              drawChart();
            });
          }
        }
      }
      
      // Always fetch all threats to display in table below chart
      const threatsResponse = await fetch(`${apiBase}/threats`);
      if (threatsResponse.ok) {
        const threatsData = await threatsResponse.json();
        allThreats = threatsData || [];
      }
    } catch (e) {
      // Treat aborts and errors gracefully
      if (e instanceof Error && e.name !== 'AbortError') {
        error = e instanceof Error ? e.message : 'Unknown error';
      }
    } finally {
      loading = false;
    }
  });
</script>

<div id="application-content-area">
  <div class="page-title">
    <h1 class="heading heading_1">The Big Picture</h1>
    <p class="subtitle">Top 5 Risk Threats - Value at Risk (VaR) before and after mitigation</p>
  </div>

  {#if loading}
    <div class="message">Loading data...</div>
  {:else if error}
    <div class="message message-error">Error: {error}</div>
  {:else}
    {#if chartThreats.length > 0}
      <div class="chart-container">
        <div id="curve_chart" class="google-chart"></div>
      </div>
      
      <!-- Summary table for chart data -->
      <div class="summary-section">
        <h2 class="heading heading_2">Risk Summary (Top 5)</h2>
        <div class="summary-table">
          <table>
            <thead>
              <tr>
                <th>Threat</th>
                <th>VaR Before Mitigation</th>
                <th>VaR After Mitigation</th>
                <th>Mitigation Level</th>
                <th>Residual Risk %</th>
              </tr>
            </thead>
            <tbody>
              {#each chartThreats as threat}
                <tr>
                  <td class="threat-name">{threat.threat_tag}: {threat.threat_name}</td>
                  <td class="number">{threat.var_before_mitigation.toLocaleString('en-US')}</td>
                  <td class="number">{threat.var_after_mitigation.toLocaleString('en-US')}</td>
                  <td class="center">{threat.mitigation_level}</td>
                  <td class="center">{threat.residual_risk_pct.toFixed(1)}%</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}
    
    <!-- Always show all threats table -->
    {#if allThreats.length > 0}
      <div class="threats-section">
        <h2 class="heading heading_2">All Threats</h2>
        <div class="threats-table">
          <table>
            <thead>
              <tr>
                <th>Tag</th>
                <th>Name</th>
                <th>Domain</th>
                <th>Damage Description</th>
                <th>Probability (%)</th>
                <th>Created At</th>
              </tr>
            </thead>
            <tbody>
              {#each allThreats as threat}
                <tr>
                  <td class="threat-tag">{threat.tag || '-'}</td>
                  <td class="threat-name">{threat.name}</td>
                  <td class="threat-domain">{threat.domain || '-'}</td>
                  <td class="threat-description">{threat.damage_description || '-'}</td>
                  <td class="center">{threat.probability || '-'}</td>
                  <td class="date">{threat.created_at ? new Date(threat.created_at).toLocaleDateString() : '-'}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {:else if chartThreats.length === 0}
      <div class="message">No threat entities</div>
    {/if}
  {/if}
</div>

<style>
  .subtitle {
    color: #666;
    font-size: 0.95rem;
    margin-top: 0.5rem;
  }
  
  .chart-container {
    background: white;
    padding: 2rem;
    border-radius: 8px;
    border: 1px solid #e0e0e0;
    margin: 2rem 0;
    display: flex;
    flex-direction: column;
    gap: 2rem;
    width: 75%;
  }
  
  .google-chart {
    width: 100%;
    height: 500px;
  }
  
  :global(#curve_chart text) {
    font-weight: 400 !important;
  }
  
  .threats-section {
    background: white;
    padding: 2rem;
    border-radius: 8px;
    border: 1px solid #e0e0e0;
    margin-top: 2rem;
    width: 100%;
  }
  
  .summary-section {
    background: white;
    padding: 2rem;
    border-radius: 8px;
    border: 1px solid #e0e0e0;
    margin-top: 2rem;
    width: 75%;
  }
  
  .summary-table {
    overflow-x: auto;
    margin-top: 1rem;
  }
  
  .threats-table {
    overflow-x: auto;
    margin-top: 1rem;
  }
  
  .threats-table table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8em;
    font-weight: 400;
  }
  
  .threats-table th {
    background-color: #f5f5f5;
    padding: 0.75rem;
    text-align: center;
    font-weight: 400;
    border-bottom: 2px solid #ddd;
  }
  
  .threats-table th:first-child {
    text-align: left;
  }
  
  .threats-table td {
    padding: 0.75rem;
    border-bottom: 1px solid #eee;
    font-weight: 400;
  }
  
  .threats-table tr:hover {
    background-color: #fafafa;
  }
  
  .threat-tag {
    text-align: center;
    font-weight: 600;
  }
  
  .threat-domain {
    text-align: center;
  }
  
  .threat-description {
    max-width: 300px;
    white-space: normal;
  }
  
  .date {
    text-align: center;
  }
  
  .summary-table table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8em;
    font-weight: 400;
  }
  
  .summary-table th {
    background-color: #f5f5f5;
    padding: 0.75rem;
    text-align: center;
    font-weight: 400;
    border-bottom: 2px solid #ddd;
  }
  
  .summary-table th:first-child {
    text-align: left;
  }
  
  .summary-table td {
    padding: 0.75rem;
    border-bottom: 1px solid #eee;
    font-weight: 400;
  }
  
  .summary-table tr:hover {
    background-color: #fafafa;
  }
  
  .threat-name {
    font-weight: 400;
    max-width: 300px;
  }
  
  .number {
    text-align: center;
  }
  
  .center {
    text-align: center;
  }
  
  .message {
    padding: 1rem;
    background-color: #f5f5f5;
    border-radius: 4px;
    color: #666;
  }
  
  .message-error {
    background-color: #fee;
    color: #c33;
  }
</style>
