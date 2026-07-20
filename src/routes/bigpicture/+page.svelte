<script lang="ts">
  import { onMount } from 'svelte';
import { API_BASE } from '$lib/config';
  
  let threats: any[] = [];
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
    if (!threats.length) return;
    
    const container = document.getElementById('curve_chart');
    if (!container) return;
    
    const data = google.visualization.arrayToDataTable([
      ['Threat', 'VaR Before Mitigation', 'VaR After Mitigation'],
      ...threats.map(t => [t.threat_tag, t.var_before_mitigation, t.var_after_mitigation])
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
      // Add a 5-second timeout to prevent hanging
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      
      const response = await fetch(`${apiBase}/query/THRIM`, { signal: controller.signal });
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        // If 404 or other error, treat as no data
        if (response.status === 404 || response.status === 400) {
          threats = [];
        } else {
          throw new Error(`Server error: ${response.status}`);
        }
      } else {
        const allData = await response.json();
        // Get top 5 rows
        threats = allData.slice(0, 5);
        
        // Only load Google Charts if we have threat data
        if (threats.length > 0) {
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
    } catch (e) {
      // Treat aborts and errors as "no data"
      if (e instanceof Error && e.name === 'AbortError') {
        threats = [];
      } else {
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
  {:else if threats.length === 0}
    <div class="message">No threat entities</div>
  {:else}
    <div class="chart-container">
      <div id="curve_chart" class="google-chart"></div>
    </div>
    
    <!-- Summary table -->
    <div class="summary-section">
      <h2 class="heading heading_2">Risk Summary</h2>
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
            {#each threats as threat}
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
