import os
import sys
import importlib

# 🛡️ Compatibility monkeypatch for huggingface_hub HfFolder removal in newer versions
try:
    import huggingface_hub
    if not hasattr(huggingface_hub, "HfFolder"):
        try:
            from huggingface_hub.utils import HfFolder as _HfFolder
            setattr(huggingface_hub, "HfFolder", _HfFolder)
        except Exception:
            class MockHfFolder:
                @staticmethod
                def get_token():
                    return os.environ.get("HF_TOKEN")
                @staticmethod
                def save_token(token):
                    pass
                @staticmethod
                def delete_token():
                    pass
            setattr(huggingface_hub, "HfFolder", MockHfFolder)
except Exception:
    pass

# 🛡️ Starlette Jinja2Templates TemplateResponse compatibility fix for Gradio 4 + Starlette 0.36+
try:
    from starlette.templating import Jinja2Templates
    _orig_template_response = Jinja2Templates.TemplateResponse
    def _patched_template_response(self, *args, **kwargs):
        # Gradio 4 calls TemplateResponse(name: str, context: dict)
        # Starlette 0.36+ expects TemplateResponse(request: Request, name: str, context: dict)
        if len(args) >= 2 and isinstance(args[0], str) and isinstance(args[1], dict):
            name = args[0]
            context = args[1]
            request = kwargs.get("request") or context.get("request")
            if request:
                return _orig_template_response(self, request=request, name=name, context=context)
        return _orig_template_response(self, *args, **kwargs)
    Jinja2Templates.TemplateResponse = _patched_template_response
except Exception:
    pass

try:
    spaces = importlib.import_module("spaces")
except Exception:
    class MockSpaces:
        @staticmethod
        def GPU(*args, **kwargs):
            def decorator(func):
                return func
            return decorator
    spaces = MockSpaces()

import gradio as gr
from fastapi.middleware.cors import CORSMiddleware
from main import app as fastapi_app

# Top-level Gradio Blocks for Hugging Face ZeroGPU SDK
with gr.Blocks(title="PhonkBlaster ZeroGPU Microservice") as demo:
    gr.Markdown("# 🏎️ PhonkBlaster Studio — ZeroGPU Microservice")
    gr.Markdown("🟢 **Status:** Microservice Online & Active | **GPU:** ZeroGPU Dynamic Acceleration Enabled")
    gr.Markdown("High-speed NVENC beat-synced phonk video rendering engine with 720p/1080p tier resolution output.")

# Attach CORS & all FastAPI endpoints (/render, /status, /download, /clean-watermark) to Gradio ASGI app
try:
    demo.app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    demo.app.include_router(fastapi_app.router)
except Exception:
    pass

if __name__ == "__main__":
    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
    )
