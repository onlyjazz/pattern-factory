<script lang="ts">
  import { onMount } from "svelte";
  import CodeMirror from "svelte-codemirror-editor";
  import { basicSetup } from "@codemirror/basic-setup";
  import { python } from "@codemirror/lang-python";
  import { autocompletion, CompletionContext } from "@codemirror/autocomplete";
  import { dslCode, dslFilePath, isDirty } from "$lib/stores/dslStore";
  import { get } from "svelte/store";
  import { saveDslFile, fetchAutocompleteItems } from "$lib/api";
  import { acts } from '@tadashi/svelte-notification';
  import { fileHandle } from "./stores/fileHandleStore";
  import Page from "../routes/+page.svelte";

  export let height: string = '600px';

  let extensions = [basicSetup, python()];
  $: selectedFileName = $dslFilePath ? $dslFilePath.split('/').pop() : null;

  async function loadLocalYaml() {
    try {
      // Ask the user to pick a file
      const [handle] = await (window as any).showOpenFilePicker({
        types: [{ description: 'YAML', accept: { 'application/x-yaml': ['.yaml', '.yml'] } }]
      });

      const file = await handle.getFile();
      const text = await file.text();

      dslCode.set(text);
      fileHandle.set(handle);
      dslFilePath.set(handle.name);
      selectedFileName = handle.name;
      isDirty.set(false);

      console.log('[loadLocalYaml] picked ->', handle.name);
    } catch (err) {
      console.warn('[loadLocalYaml] cancelled or failed:', err);
    }
  }

  // Helper to write using File System Access API (with permission check)
  async function writeToHandle(handle: FileSystemFileHandle, contents: string) {
    // Request readwrite permission if needed
    // @ts-ignore
    const perm = await handle.requestPermission?.({ mode: 'readwrite' });
    if (perm && perm !== 'granted') throw new Error('Permission denied');

    // @ts-ignore
    const writable = await handle.createWritable();
    await writable.write(contents)
    await writable.close();
  }

  // Editor Changes
  function handleChange(e: CustomEvent<string>) {
    dslCode.set(e.detail);
    isDirty.set(true);
  }

  // Save As function - prompts user to select where to save
  async function saveAsLocal() {
    const code = get(dslCode);
    if (!code) {
      acts.add({ message: 'No code to save', mode: 'warning', lifetime: 3 });
      return;
    }

    try {
      // @ts-ignore
      const handle = await window.showSaveFilePicker({
        suggestedName: 'dsl_config.yaml',
        types: [
          {
            description: 'YAML Files',
            accept: { 'text/yaml': ['.yaml', '.yml'] },
          },
        ],
      });

      await writeToHandle(handle, code);
      
      // Update stores with new file info
      fileHandle.set(handle);
      dslFilePath.set(handle.name);
      isDirty.set(false);
      
      acts.add({ message: `Saved to ${handle.name}`, mode: 'success', lifetime: 3 });
    } catch (err) {
      // User cancelled or error occurred
      console.warn('[saveAsLocal] Save cancelled or failed:', err);
      if (err.name !== 'AbortError') {
        acts.add({ message: 'Save failed', mode: 'error', lifetime: 3 });
      }
    }
  }

  // Save logic
  async function handleSave() {
    const code = get(dslCode);
    const handle = get(fileHandle);

    if (!code) {
      acts.add({ message: 'No code to save', mode: 'warning', lifetime: 3 });
      return;
    }

    // 1) If there is a handle, overwrite locally
    if (handle) {
      try {
        await writeToHandle(handle, code);
        acts.add({ message: 'Saved (local)', mode: 'success', lifetime: 3 });
        isDirty.set(false);
        return;
      } catch (e) {
        console.error('[handleSave] local save failed:', e);
        acts.add({ message: 'Local save failed. Try Save As.', mode: 'error', lifetime: 5 });
      }
    }

    // 2) No handle? Prompt Save As locally
    await saveAsLocal();
  }


  // Autocomplete
  async function setupCompletions() {
    const items = await fetchAutocompleteItems();

    const completions = items.map((item) => ({
      label: item.item_id,
      type: 'keyword',
      info: item.description,
    }));

    const completionSource = (context: CompletionContext) => {
      const word = context.matchBefore(/\w*/);
      if (!word || (word.from === word.to && !context.explicit)) return null;
      return { from: word.from, options: completions };
    };

    extensions = [basicSetup, python(), autocompletion({ override: [completionSource] })];
  }

  onMount(() => {
    setupCompletions();
  });
</script>

<!-- Code Editor -->
<div class="grid-row">
  <div class="grid-col grid-col_24">
    <CodeMirror 
      bind:value={$dslCode}
      extensions={extensions}
      on:change={handleChange}
      styles={{
        "&": {
          width: "100%",
          maxWidth: "100%",
          height
        }
      }}
    />
    
    <div class="button-container">
      <!-- Save Button -->
      <button class="button" type="submit" style="margin-top: 1rem;" onclick={handleSave} disabled={!$isDirty}>Save</button>
      <!-- button class="button" style="margin-top: 1rem;" onclick={saveAsLocal}>Save As</button -->
      <button class="button" style="margin-top: 1rem;" onclick={loadLocalYaml}>Load DSL</button>

      <!-- Show selected file -->
      {#if selectedFileName}
        <p style="margin-top: 1rem; font-size: 0.9rem; color: gray;">
          Selected file: {selectedFileName}
        </p>
      {:else}
        <p style="margin-top: 1rem; font-size: 0.9rem; color: gray;">
          No File Loaded
        </p>
      {/if}
    </div>
  </div>
</div>

<style>
  .button:disabled {
    background-color: gray;
  }
</style>