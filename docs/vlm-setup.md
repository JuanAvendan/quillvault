# Local vision-language model (VLM) setup

The `vlm` engine talks to a [llama.cpp](https://github.com/ggml-org/llama.cpp) server
running **on the same machine**. QuillVault refuses any endpoint that does not resolve
to a loopback address (`127.0.0.1`, `::1`, `localhost`) and ignores proxy variables.

Recommended model: **Qwen2.5-VL-7B-Instruct** (Apache-2.0), Q4_K_M quantisation —
4.7 GB + 0.85 GB vision projector, fits an 8 GB GPU.

> ⚠️ Check the licence of any other model you use. Some sizes/versions of popular VLMs
> ship under research-only or custom licences.

## Windows + AMD/Intel/NVIDIA GPU (Vulkan)

1. Download `llama-<build>-bin-win-vulkan-x64.zip` from the
   [llama.cpp releases](https://github.com/ggml-org/llama.cpp/releases) and unzip it,
   e.g. to `C:\Tools\llama.cpp`.
2. Download the model files once (only public weights travel over the network):

   ```powershell
   uv run hf download ggml-org/Qwen2.5-VL-7B-Instruct-GGUF `
     Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf mmproj-Qwen2.5-VL-7B-Instruct-Q8_0.gguf `
     --local-dir $env:LOCALAPPDATA\QuillVault\models\qwen2.5-vl-7b
   ```

3. Start the server — bound to loopback only:

   ```powershell
   $m = "$env:LOCALAPPDATA\QuillVault\models\qwen2.5-vl-7b"
   C:\Tools\llama.cpp\llama-server.exe `
     -m "$m\Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf" `
     --mmproj "$m\mmproj-Qwen2.5-VL-7B-Instruct-Q8_0.gguf" `
     --host 127.0.0.1 --port 8080 -ngl 99 -c 8192
   ```

   `-ngl 99` offloads all layers to the GPU. If you run out of VRAM, lower it (e.g. `-ngl 24`).

4. Check and use it:

   ```powershell
   uv run quillvault doctor --vlm-url http://127.0.0.1:8080
   uv run quillvault extract scan.jpg --engine vlm
   uv run quillvault extract scan.jpg --engine vlm --vlm-mode lines   # with boxes, slower
   ```

## Linux

Use the Vulkan or ROCm build of llama.cpp with the same command line.

## Why every VLM line is flagged for review

A VLM produces fluent text and has no calibrated per-line confidence. It can "read"
a plausible word that is not on the page (hallucination). With clinical data that is
unacceptable without a human check, so QuillVault always marks VLM output as
*needs review*. The prompt also asks the model to write `[?]` for illegible words
instead of guessing.
