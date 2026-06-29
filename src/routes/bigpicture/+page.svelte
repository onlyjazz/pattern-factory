<script lang="ts">
  import { onMount } from 'svelte';
  
  let threats: any[] = [];
  let loading = true;
  let error = '';
  const apiBase = 'http://localhost:8000';
  
  // Chart dimensions
  const chartWidth = 1000;
  const chartHeight = 400;
  const padding = { top: 40, right: 40, bottom: 100, left: 60 };
  const innerWidth = chartWidth - padding.left - padding.right;
  const innerHeight = chartHeight - padding.top - padding.bottom;
  
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
  });
  
  // Calculate scales
  function getMaxValue(): number {
    if (threats.length === 0) return 0;
    return Math.max(
      ...threats.map(t => Math.max(t.var_before_mitigation, t.var_after_mitigation))
    );
  }
  
  function scaleY(value: number): number {
    const max = getMaxValue();
    if (max === 0) return 0;
    return (value / max) * innerHeight;
  }
  
  function formatNumber(num: number): string {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1) + 'M';
    }
    if (num >= 1000) {
      return (num / 1000).toFixed(0) + 'K';
    }
    return num.toString();
  }
  
  // SVG coordinates
  function getBarX(threatIndex: number, isAfter: boolean): number {
    const barWidth = 30;
    const barGap = 8;
    const groupWidth = barWidth * 2 + barGap; // width of one group (2 bars + gap)
    const groupSpacing = innerWidth / threats.length;
    const groupX = padding.left + (threatIndex * groupSpacing) + (groupSpacing - groupWidth) / 2;
    return groupX + (isAfter ? barWidth + barGap : 0);
  }
  
  function getBarY(value: number): number {
    return padding.top + innerHeight - scaleY(value);
  }
  
  function getBarHeight(value: number): number {
    return scaleY(value);
  }
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
      <svg {chartWidth} {chartHeight} class="chart">
        <!-- Y-axis -->
        <line
          x1={padding.left}
          y1={padding.top}
          x2={padding.left}
          y2={padding.top + innerHeight}
          stroke="#333"
          stroke-width="2"
        />
        
        <!-- X-axis -->
        <line
          x1={padding.left}
          y1={padding.top + innerHeight}
          x2={padding.left + innerWidth}
          y2={padding.top + innerHeight}
          stroke="#333"
          stroke-width="2"
        />
        
        <!-- Y-axis labels (values) -->
        {#each [0, 0.25, 0.5, 0.75, 1] as scale}
          {@const value = getMaxValue() * scale}
          {@const y = padding.top + innerHeight - (scale * innerHeight)}
          <text
            x={padding.left - 10}
            y={y}
            text-anchor="end"
            dominant-baseline="middle"
            font-size="12"
            fill="#666"
          >
            {formatNumber(value)}
          </text>
          <line
            x1={padding.left - 5}
            y1={y}
            x2={padding.left}
            y2={y}
            stroke="#333"
            stroke-width="1"
          />
        {/each}
        
        <!-- Bars for each threat -->
        {#each threats as threat, idx}
          <!-- Before mitigation bar (blue) -->
          <rect
            x={getBarX(idx, false)}
            y={getBarY(threat.var_before_mitigation)}
            width="30"
            height={getBarHeight(threat.var_before_mitigation)}
            fill="#2563eb"
            opacity="0.8"
            class="bar"
          />
          
          <!-- After mitigation bar (green) -->
          <rect
            x={getBarX(idx, true)}
            y={getBarY(threat.var_after_mitigation)}
            width="30"
            height={getBarHeight(threat.var_after_mitigation)}
            fill="#16a34a"
            opacity="0.8"
            class="bar"
          />
        {/each}
        
        <!-- X-axis labels (threat names) -->
        {#each threats as threat, idx}
          {@const groupSpacing = innerWidth / threats.length}
          {@const groupX = padding.left + (idx * groupSpacing) + groupSpacing / 2}
          <text
            x={groupX}
            y={padding.top + innerHeight + 20}
            text-anchor="middle"
            font-size="11"
            fill="#333"
            class="threat-label"
          >
            {threat.threat_tag}
          </text>
        {/each}
      </svg>
      
      <!-- Legend -->
      <div class="legend">
        <div class="legend-item">
          <div class="legend-color" style="background-color: #2563eb;"></div>
          <span>VaR Before Mitigation</span>
        </div>
        <div class="legend-item">
          <div class="legend-color" style="background-color: #16a34a;"></div>
          <span>VaR After Mitigation</span>
        </div>
      </div>
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
  
  .chart {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }
  
  .bar {
    transition: opacity 0.2s ease;
  }
  
  .bar:hover {
    opacity: 1 !important;
  }
  
  .threat-label {
    font-weight: 500;
  }
  
  .legend {
    display: flex;
    gap: 2rem;
    justify-content: center;
  }
  
  .legend-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
  }
  
  .legend-color {
    width: 20px;
    height: 20px;
    border-radius: 3px;
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
