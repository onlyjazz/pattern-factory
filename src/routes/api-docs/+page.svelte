<script lang="ts">
  import { API_BASE } from '$lib/config';

  const swaggerUrl = `${API_BASE}/docs`;
</script>

<div id="application-content-area">
  <div class="page-title">
    <h1 class="heading heading_1">API Documentation</h1>
    <p class="subtitle">Interactive Swagger API documentation</p>
  </div>

  <div class="docs-wrapper">
    <iframe
      src={swaggerUrl}
      title="Swagger UI - Interactive API Documentation"
      sandbox="allow-same-origin allow-scripts allow-popups allow-forms allow-modals"
    />
  </div>
</div>

<style>
  .subtitle {
    color: #666;
    font-size: 0.95rem;
    margin-top: 0.5rem;
  }

  .docs-wrapper {
    width: 100%;
    height: calc(100vh - 200px);
    margin-top: 2rem;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    overflow: hidden;
  }

  .docs-wrapper iframe {
    width: 100%;
    height: 100%;
    border: none;
  }
</style>
