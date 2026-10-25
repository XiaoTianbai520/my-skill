# Your machine

Detected 2026-10-25 for HuiMeng acceptance. User starts ComfyUI manually; connect only, do not auto-start or restart.

- **ComfyUI**: Windows portable, core `M:/ComfyUI_windows_portable_nvidia/ComfyUI_windows_portable/ComfyUI`, API `http://127.0.0.1:8188`, version 0.37.0.
- **GPU**: cuda:0 NVIDIA GeForce RTX 3060 : cudaMallocAsync; VRAM 12884377600 bytes; RAM 34138939392 bytes.
- **Model drive free**: 82484953088 bytes at detection. No downloads authorized for this acceptance.
- **Models verified live**: `qwen_image_2.1_int8_convrot.safetensors`, `qwen3vl_8b_w4a8.safetensors`, `qwen_image_vae.safetensors`; query object_info before future use. Other families not inventoried.
- **Models dir**: `M:/ComfyUI_windows_portable_nvidia/ComfyUI_windows_portable/ComfyUI/models`; shared/extra model paths not exhaustively inventoried.
- **GUI workflows**: `M:/ComfyUI_windows_portable_nvidia/ComfyUI_windows_portable/ComfyUI/user/default/workflows`; `HuiMeng-M2-acceptance.json` saved.
- **Templates**: installed package `M:/ComfyUI_windows_portable_nvidia/ComfyUI_windows_portable/python_embeded/Lib/site-packages/comfyui_workflow_templates_json/templates`; separate template clone and `_quick_index.json` not configured. HuiMeng reuses its confirmed provider fixture, without replacing/updating workflows.
- **Launch**: user opens `run_nvidia_gpu.bat` in the portable parent. It runs `python_embeded/python.exe -s ComfyUI/main.py --windows-standalone-build --enable-manager`. Detected from launcher and live argv; no duplicate startup test because user selected manual startup.
- **Quirks**: sandbox socket denial does not imply API is down; retry authorized localhost inspection outside sandbox. User-approved project `.comfyui-agent.json` startPolicy is `connect`.
- **Smoke check**: current Qwen generated a 1024x1024 PNG in 50 seconds; viewed and saved in HuiMeng validation evidence. No remote key or node install/update.
