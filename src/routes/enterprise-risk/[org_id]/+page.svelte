<script lang="ts">
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { API_BASE } from '$lib/config';
  import type { Organization } from '$lib/types/models';
  import {
    buildEnterpriseRiskDocDefinition,
    formatNumber,
    formatPercentCompact,
    getEnterpriseRiskPdfFileName,
    SLE_LEGEND,
    threatSle,
    threatSleAfterMitigation
  } from '$lib/riskReportPdf';
  import { captureChartImage, downloadPdf, loadImageAsDataUrl } from '$lib/pdfExport';

  interface EnterpriseRiskResponse {
    org_metadata: {
      id: number;
      name: string;
      size: number;
      tier: number;
      funding: number;
      estimated_annual_sales: number;
    };
    threats: Array<{
      threat_id: number;
      model_id: number;
      model_name: string;
      product_id: number;
      product_name: string;
      threat_tag: string;
      threat_name: string;
      damage_description: string;
      threat_probability: number;
      affected_asset_count: number;
      gross_sle: number;
      current_sle: number;
      current_mitigation_pct: number;
      current_residual_exposure_pct: number;
      target_sle: number;
      target_mitigation_pct: number;
      target_residual_exposure_pct: number;
      sle: number;
      sle_after_mitigation: number;
      rank_in_org: number;
    }>;
  }

  let chartThreats: any[] = [];
  let allThreats: any[] = [];
  let orgMetadata: EnterpriseRiskResponse['org_metadata'] | null = null;
  let loading = true;
  let error = '';
  let generatingPdf = false;
  let pdfError = '';
  const apiBase = API_BASE;

  async function navigateToModelRisk(model_id: number) {
    await goto(`/model-risk/${model_id}`);
  }
  
  function formatCurrency(value?: number): string {
    if (value === undefined || value === null) return '-';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0
    }).format(value);
  }

  async function generatePdf() {
    if (generatingPdf) return;
    generatingPdf = true;
    pdfError = '';
    try {
      const [chartImage, logoImage] = await Promise.all([
        captureChartImage('enterprise_chart'),
        loadImageAsDataUrl('/img/opencro-logo.png')
      ]);
      const docDefinition = buildEnterpriseRiskDocDefinition({
        org: orgMetadata,
        chartThreats,
        allThreats,
        chartImage,
        logoImage
      });
      await downloadPdf(docDefinition, getEnterpriseRiskPdfFileName(orgMetadata));
    } catch (e) {
      console.error('Failed to generate PDF', e);
      pdfError = e instanceof Error ? e.message : 'Failed to generate PDF';
    } finally {
      generatingPdf = false;
    }
  }

  async function loadEnterpriseRisk(org_id: number): Promise<void> {
    loading = true;
    error = '';
    try {
      const response = await fetch(`${apiBase}/enterprise-risk/${org_id}`);
      if (response.ok) {
        const data: EnterpriseRiskResponse = await response.json();
        orgMetadata = data.org_metadata;
        
        // Filter and sort threats
        const validThreats = data.threats.filter((t: any) => 
          t.gross_sle !== null && t.gross_sle !== undefined
        );
        
        const sortedThreats = validThreats.sort(
          (a: any, b: any) =>
            (threatSle(b) ?? 0) - (threatSle(a) ?? 0)
        );
        chartThreats = sortedThreats.slice(0, 5);
        allThreats = sortedThreats;
        
        // Load Google Charts if we have valid threat data
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
      } else if (response.status === 404) {
        error = 'Organization not found';
      } else {
        error = 'Failed to load enterprise risk data';
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Unknown error';
    } finally {
      loading = false;
    }
  }

  function drawChart() {
    if (!chartThreats.length) return;
    
    const container = document.getElementById('enterprise_chart');
    if (!container) return;
    
    const data = google.visualization.arrayToDataTable([
      ['Threat', 'SLE', 'SLE after mitigation'],
      ...chartThreats.map((t) => {
        return [t.threat_tag, threatSle(t) ?? 0, threatSleAfterMitigation(t) ?? 0];
      })
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
        title: 'SLE ($)',
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
      const orgId = parseInt($page.params.org_id, 10);
      if (isNaN(orgId)) {
        error = 'Invalid organization ID';
        loading = false;
        return;
      }
      await loadEnterpriseRisk(orgId);
    } catch (e) {
      error = 'Failed to initialize page';
      console.error(e);
    }
  });
</script>

<div id="application-content-area">
  <div class="page-title">
    {#if !loading && !error}
      <button
        type="button"
        class="button button_green"
        onclick={generatePdf}
        disabled={generatingPdf}
        title="Download this enterprise risk report as PDF"
      >
        Download PDF
      </button>
    {/if}
    <h1 class="heading heading_1">Enterprise Risk</h1>
    <p class="subtitle">Top 5 Single Loss Events Across Products</p>
    {#if pdfError}
      <div class="message message-error">Error: {pdfError}</div>
    {/if}

    {#if orgMetadata}
      <div class="enterprise-header">
        <table class="enterprise-header-table">
          <tbody>
            <tr>
              <td class="label">Organization</td>
              <td class="value">{orgMetadata.name}</td>
            </tr>
            <tr>
              <td class="label">Funding</td>
              <td class="value">{formatCurrency(orgMetadata.funding)}</td>
            </tr>
            <tr>
              <td class="label">Estimated Annual Sales</td>
              <td class="value">{formatCurrency(orgMetadata.estimated_annual_sales)}</td>
            </tr>
            <tr>
              <td class="label">Valuation (Size)</td>
              <td class="value">{formatCurrency(orgMetadata.size)}</td>
            </tr>
            <tr>
              <td class="label">Tier</td>
              <td class="value">{orgMetadata.tier === 1 ? 'Enterprise' : orgMetadata.tier === 2 ? 'Mid-Market' : 'Startup'}</td>
            </tr>
          </tbody>
        </table>
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
        <div id="enterprise_chart" class="google-chart"></div>
      </div>
    {/if}
    
    <!-- Always show all threats table -->
    {#if allThreats.length > 0}
      <div class="threats-section">
        <div class="threats-table">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Product</th>
                <th>Damage Description</th>
                <th>Probability</th>
                <th>Assets at risk ($)</th>
                <th>SLE ($)</th>
                <th>Target mitigation</th>
                <th>SLE after mitigation ($)</th>
              </tr>
            </thead>
            <tbody>
              {#each allThreats as threat}
                <tr>
                  <td class="threat-name">{threat.threat_name}</td>
                  <td
                    class="product-name"
                    role="button"
                    tabindex="0"
                    onclick={() => navigateToModelRisk(threat.model_id)}
                    onkeydown={(e) => e.key === 'Enter' && navigateToModelRisk(threat.model_id)}
                    title="Navigate to model risk details"
                  >
                    {threat.product_name}
                  </td>
                  <td class="threat-description">{threat.damage_description || '-'}</td>
                  <td class="center">{formatPercentCompact(threat.threat_probability)}</td>
                  <td class="number">{formatNumber(threat.gross_sle)}</td>
                  <td class="number">{formatNumber(threatSle(threat))}</td>
                  <td class="center">{formatPercentCompact(threat.target_mitigation_pct)}</td>
                  <td class="number">{formatNumber(threatSleAfterMitigation(threat))}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        <p class="report-note">{SLE_LEGEND}</p>
      </div>
    {:else if chartThreats.length === 0}
      <div class="message">No threat entities for this organization</div>
    {/if}
  {/if}
</div>

<style>
  .subtitle {
    color: #666;
    font-size: 0.95rem;
    margin-top: 0.5rem;
  }
  
  .enterprise-header {
    margin-top: 1.5rem;
    padding: 1rem;
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
  }
  
  .enterprise-header-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }
  
  .enterprise-header-table tbody tr {
    border-bottom: 1px solid #eee;
  }
  
  .enterprise-header-table td {
    padding: 0.75rem;
  }
  
  .enterprise-header-table td.label {
    font-weight: 600;
    width: 200px;
    color: #333;
  }
  
  .enterprise-header-table td.value {
    color: #666;
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
  
  :global(#enterprise_chart text) {
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
  
  .threats-table th:first-child,
  .threats-table th:nth-child(2) {
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
  
  .threat-description {
    max-width: 300px;
    white-space: normal;
  }
  
  .threat-name {
    font-weight: 400;
    max-width: 300px;
  }
  
  .product-name {
    font-weight: 400;
    text-align: left;
    color: #0066cc;
    cursor: pointer;
    text-decoration: underline;
  }

  .product-name:hover {
    color: #0052a3;
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
