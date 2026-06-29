<script lang="ts">
  import { onMount } from 'svelte';
  
  let threats: any[] = [];
  let loading = true;
  let error = '';
  let chartInitialized = false;
  const apiBase = 'http://localhost:8000';
  
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
      legend: { position: 'bottom' },
      hAxis: {
        title: 'Threats',
        titleTextStyle: { color: '#333' }
      },
      vAxis: {
        title: 'Value (VaR)',
        titleTextStyle: { color: '#333' },
        format: '#,###'
      },
      colors: ['#2563eb', '#16a34a'],
      chartArea: { width: '75%', height: '75%' },
      bar: { groupWidth: '75%' }
    };
    
    const chart = new google.visualization.ColumnChart(container);
    chart.draw(data, options);
  }
  
  onMount(async () => {
    try {
      const response = await fetch(`${apiBase}/query/THRIM`);
      if (!response.ok) throw new Error('Failed to fetch THRIM data');
      const allData = await response.json();
      
      // Get top 5 rows
      threats = allData.slice(0, 5);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Unknown error';
    } finally {
      loading = false;
    }
    
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
  });
</script>

<div id="application-content-area">
  <div class="page-title">
    <h1 class="heading heading_1">The Big Picture</h1>
    <p class="subtitle">Top 5 Risk Threats - VaR Before and After Mitigation</p>
  </div>

  {#if loading}
    <div class="message">Loading data...</div>
  {:else if error}
    <div class="message message-error">Error: {error}</div>
  {:else if threats.length === 0}
    <div class="message">No data found</div>
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
              <th>Risk Reduction</th>
              <th>Residual Risk %</th>
            </tr>
          </thead>
          <tbody>
            {#each threats as threat}
              <tr>
                <td class="threat-name">{threat.threat_tag}: {threat.threat_name}</td>
                <td class="number">{threat.var_before_mitigation.toLocaleString('en-US')}</td>
                <td class="number">{threat.var_after_mitigation.toLocaleString('en-US')}</td>
                <td class="center">{threat.risk_reduction}</td>
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
  }
  
  .google-chart {
    width: 100%;
    height: 500px;
  }
  
  .summary-section {
    background: white;
    padding: 2rem;
    border-radius: 8px;
    border: 1px solid #e0e0e0;
    margin-top: 2rem;
  }
  
  .summary-table {
    overflow-x: auto;
    margin-top: 1rem;
  }
  
  .summary-table table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
  }
  
  .summary-table th {
    background-color: #f5f5f5;
    padding: 0.75rem;
    text-align: left;
    font-weight: 600;
    border-bottom: 2px solid #ddd;
  }
  
  .summary-table td {
    padding: 0.75rem;
    border-bottom: 1px solid #eee;
  }
  
  .summary-table tr:hover {
    background-color: #fafafa;
  }
  
  .threat-name {
    font-weight: 500;
    max-width: 300px;
  }
  
  .number {
    text-align: right;
    font-family: 'Courier New', monospace;
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
