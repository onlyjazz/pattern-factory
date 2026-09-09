<script lang="ts">
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { API_BASE } from '$lib/config';
  import type { Organization, Product } from '$lib/types/models';
  import { goto } from '$app/navigation';

  interface ModelDetail {
    id: number;
    name: string;
    product_id?: number;
    org_name?: string;
  }

  interface ModelRiskHeader {
    model_id: number;
    model_name: string;
    product: string;
    company: string;
    org_id?: number;
    sales?: number;
    funding?: number;
    valuation?: number;
    device_description?: string;
    intended_use?: string;
    competitive_advantage?: string;
  }
  
  let chartThreats: any[] = [];
  let allThreats: any[] = [];
  let header: ModelRiskHeader | null = null;
  let loading = true;
  let error = '';
  const apiBase = API_BASE;
  
  function formatCurrency(value?: number): string {
    if (value === undefined || value === null) return '-';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0
    }).format(value);
  }

  async function loadHeader(modelId: number): Promise<void> {
    try {
      const modelResponse = await fetch(`${apiBase}/models/${modelId}`);
      if (!modelResponse.ok) throw new Error('Model not found');

      const model: ModelDetail = await modelResponse.json();
      let product: Product | null = null;
      let organization: Organization | null = null;

      if (model.product_id) {
        const productResponse = await fetch(`${apiBase}/products/${model.product_id}`);
        if (productResponse.ok) {
          product = await productResponse.json();
        }
      }

      if (product?.org_id) {
        const organizationResponse = await fetch(`${apiBase}/orgs/${product.org_id}`);
        if (organizationResponse.ok) {
          organization = await organizationResponse.json();
        }
      }

      header = {
        model_id: model.id,
        model_name: model.name,
        product: product?.device || '-',
        company: organization?.name || product?.company || '-',
        org_id: organization?.id,
        sales: organization?.estimated_annual_sales,
        funding: organization?.funding,
        valuation: organization?.size,
        device_description: product?.device_description,
        intended_use: product?.intended_use,
        competitive_advantage: product?.superiority
      };
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load model';
      console.error(e);
    }
  }

  async function navigateToOrgRisk(org_id: number | undefined) {
    if (!org_id) {
      error = 'Organization not available for this model';
      return;
    }
    await goto(`/enterprise-risk/${org_id}`);
  }
  
  function drawChart() {
    if (!chartThreats.length) return;
    
    const container = document.getElementById('curve_chart');
    if (!container) return;
    
    const data = google.visualization.arrayToDataTable([
      ['Threat', 'Gross SLE', 'Target SLE'],
      ...chartThreats.map(t => [t.threat_tag, t.gross_sle, t.target_sle])
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
        title: 'Single Loss Expectancy (SLE)',
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
      const modelId = parseInt($page.params.model_id, 10);
      if (isNaN(modelId)) {
        error = 'Invalid model ID';
        loading = false;
        return;
      }

      await loadHeader(modelId);
      
      // Fetch threat impact data from THRIM view
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);
      
      const response = await fetch(`${apiBase}/query/THRIM`, { signal: controller.signal });
      clearTimeout(timeoutId);
      
      if (response.ok) {
        const allData = await response.json();
        
        const validThreats = allData.filter((t: any) => 
          t.gross_sle !== null && t.gross_sle !== undefined
        );
        
        const sortedThreats = validThreats.sort((a: any, b: any) => (b.gross_sle || 0) - (a.gross_sle || 0));
        chartThreats = sortedThreats.slice(0, 5);
        allThreats = sortedThreats;
        
        if (chartThreats.length > 0) {
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
    <h1 class="heading heading_1">Model Risk</h1>
    <p class="subtitle">Top 5 Single Loss Events (SLE)</p>
    {#if header}
      <div class="model-risk-header">
        <table class="model-risk-header-table">
          <tbody>
            <tr>
              <td class="label">Model</td>
              <td class="value">{header.model_name}</td>
            </tr>
            <tr>
              <td class="label">Company</td>
              <td class="value">
                {#if header.org_id}
                  <button 
                    type="button"
                    class="link-button"
                    onclick={() => navigateToOrgRisk(header.org_id)}
                    title="Navigate to organization enterprise risk"
                  >
                    {header.company}
                  </button>
                {:else}
                  {header.company}
                {/if}
              </td>
            </tr>
            <tr>
              <td class="label">Sales</td>
              <td class="value">{formatCurrency(header.sales)}</td>
            </tr>
            <tr>
              <td class="label">Funding</td>
              <td class="value">{formatCurrency(header.funding)}</td>
            </tr>
            <tr>
              <td class="label">Valuation</td>
              <td class="value">{formatCurrency(header.valuation)}</td>
            </tr>
            <tr>
              <td class="label">Product</td>
              <td class="value">{header.product}</td>
            </tr>
            <tr>
              <td class="label">Competitive Advantage</td>
              <td class="value">{header.competitive_advantage || '-'}</td>
            </tr>
          </tbody>
        </table>
        {#if header.device_description || header.intended_use}
          <table class="model-risk-device-table">
            <tbody>
              {#if header.device_description}
                <tr>
                  <td class="label">Device Description</td>
                  <td class="value">{header.device_description}</td>
                </tr>
              {/if}
              {#if header.intended_use}
                <tr>
                  <td class="label">Intended Use</td>
                  <td class="value">{header.intended_use}</td>
                </tr>
              {/if}
            </tbody>
          </table>
        {/if}
      </div>
    {/if}
  </div>

  {#if loading}
    <div class="message">Loading data...</div>
  {:else if error}
    <div class="message message-error">Error: {error}</div>
  {:else}
    {#if chartThreats.length > 0}
      <div class="chart-container">
        <h2 class="heading heading_2">Top 5 Single Loss Events (SLE)</h2>
        <div id="curve_chart" class="google-chart"></div>
      </div>
      
    <!-- Summary table for chart data -->
      <div class="summary-section">
        <div class="summary-table">
          <table>
            <thead>
              <tr>
                <th>Threat</th>
                <th>Gross SLE</th>
                <th>Target SLE</th>
                <th>Target Mitigation %</th>
              </tr>
            </thead>
            <tbody>
              {#each chartThreats as threat}
                <tr>
                  <td class="threat-name">{threat.threat_name}</td>
                  <td class="number">{threat.gross_sle.toLocaleString('en-US')}</td>
                  <td class="number">{threat.target_sle.toLocaleString('en-US')}</td>
                  <td class="center">{threat.target_mitigation_pct.toFixed(1)}%</td>
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
                <th>Name</th>
                <th>Damage Description</th>
                <th>Gross SLE</th>
                <th>Target SLE</th>
                <th>Target Mitigation %</th>
              </tr>
            </thead>
            <tbody>
              {#each allThreats as threat}
                <tr>
                  <td class="threat-name">{threat.threat_name}</td>
                  <td class="threat-description">{threat.damage_description || '-'}</td>
                  <td class="number">{threat.gross_sle ? threat.gross_sle.toLocaleString('en-US') : '-'}</td>
                  <td class="number">{threat.target_sle ? threat.target_sle.toLocaleString('en-US') : '-'}</td>
                  <td class="center">{threat.target_mitigation_pct ? threat.target_mitigation_pct.toFixed(1) : '-'}%</td>
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

  .link-button {
    background: none;
    border: none;
    padding: 0;
    color: #0066cc;
    cursor: pointer;
    text-decoration: underline;
    font-size: inherit;
    font-family: inherit;
  }

  .link-button:hover {
    color: #0052a3;
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
  
  .threat-description {
    max-width: 300px;
    white-space: normal;
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
