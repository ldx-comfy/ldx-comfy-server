from fastapi import FastAPI
import gradio as gr

app = FastAPI()

with gr.Blocks() as demo:
    gr.Markdown("Hi friends!")

app = gr.mount_gradio_app(app, demo, path="")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
