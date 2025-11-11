<script lang="ts">
    import { onMount } from "svelte";
    import CodeMirror from "svelte-codemirror-editor";
    import { basicSetup } from "@codemirror/basic-setup";
    import { python } from "@codemirror/lang-python";
    import { autocompletion, CompletionContext } from "@codemirror/autocomplete";
    import { workflowCode, workflowFilePath, isDirty } from "$lib/stores/workflowStore";
    import { get } from "svelte/store";
    import { saveDslFile, fetchAutocompleteItems } from "$lib/api";
    import { acts } from '@tadashi/svelte-notification';
    import { fileHandle } from "./stores/fileHandleStore";
    import Page from "../routes/+page.svelte";
  
    export let height: string = '600px';
  
    let extensions = [basicSetup, python()];
    $: selectedFileName = $workflowFilePath ? $workflowFilePath.split('/').pop() : null;
  
    // Editor Changes
    function handleChange(e: CustomEvent<string>) {
      workflowCode.set(e.detail);
      isDirty.set(true);
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
  
    // Save logic
    async function handleSave() {
      const code = get(workflowCode);
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
        bind:value={$workflowCode}
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
        <button class="button" style="margin-top: 1rem;">Load Workflow</button>
  
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