"""To run
python -m src.creator.gradio_frontend
Open: http://127.0.0.1:7860
"""

import gradio as gr
import asyncio
import shutil
from src.creator.chatbot_creator import ChatbotCreator
import logging
import hydra
from hydra import compose, initialize_config_dir
from src.backend.utils.logging import setup_logging


def load_config():
    with initialize_config_dir(config_dir=str("../../../config"), job_name="Create Chatbot"):
        cfg = compose(config_name="creator")
    return cfg


cfg = load_config()
logger = logging.getLogger(__name__)
setup_logging()

creator = ChatbotCreator(cfg)

# App State
summary_cache = {"summary": "", "sim_prompt": "", "chat_prompt": ""}


# Utility wrapper for async
def run_async(coro):
    return asyncio.run(coro)


def upload_file(file):
    target = cfg.data_ingest_dir / file.name
    shutil.copy(file.name, target)
    return f"✅ File '{file.name}' saved."


def summarize():
    summary = run_async(creator.summarize_input_doc())
    summary_cache["summary"] = summary
    return summary


def set_model(model_name):
    cfg.input_doc_agent.model_name = model_name
    return f"Model set to: {model_name}"


def create_prompts():
    if not summary_cache["summary"]:
        return "No summary. Please summarize the input document first.", ""
    
    sim_prompt, chat_prompt = run_async(
        creator.create_prompt(summary_cache["summary"])
    )
    summary_cache["sim_prompt"] = sim_prompt
    summary_cache["chat_prompt"] = chat_prompt
    return sim_prompt, chat_prompt


def optimize_prompts():
    chat_prompt, sim_prompt, score, feedback = run_async(creator.optimize_prompt())
    return chat_prompt, sim_prompt, score, feedback


def finalize_prompt(decision):
    if decision == "Yes":
        return "✅ Prompts saved and ready to deploy!"
    else:
        return "🔁 You may run optimization or tweak prompts manually."


# UI
with gr.Blocks(title="🤖 Chatbot Prompt Creator") as app:
    gr.Markdown("# 🛠️ Build & Optimize Your AI Chatbot Prompt")

    with gr.Row():
        file_upload = gr.File(label="Upload Input Docs (txt, pdf, etc.)")
        upload_msg = gr.Textbox(label="Upload Status", interactive=False)

    with gr.Row():
        summarize_btn = gr.Button("🧠 Summarize")
        summary_box = gr.Textbox(label="Document Summary", lines=6)

    with gr.Row():
        create_btn = gr.Button("✨ Create Prompts")
        sim_box = gr.Textbox(label="Simulator Prompt", lines=8)
        chat_box = gr.Textbox(label="Chatbot Prompt", lines=8)

    with gr.Row():
        optimize_btn = gr.Button("🧠 Optimize Prompts")
        opt_chat = gr.Textbox(label="Optimized Chatbot Prompt", lines=8)
        opt_sim = gr.Textbox(label="Optimized Simulator Prompt", lines=8)
        score_box = gr.Number(label="Prompt Score")
        feedback_box = gr.Textbox(label="LLM Feedback", lines=4)

    with gr.Row():
        feedback = gr.Radio(["Yes", "No"], label="Use these prompts?")
        final_btn = gr.Button("Finalize")
        result_box = gr.Textbox(label="Result", interactive=False)

    # Bind buttons
    file_upload.change(upload_file, inputs=file_upload, outputs=upload_msg)
    summarize_btn.click(summarize, outputs=summary_box)
    create_btn.click(create_prompts, outputs=[sim_box, chat_box])
    optimize_btn.click(optimize_prompts, outputs=[opt_chat, opt_sim, score_box, feedback_box])
    final_btn.click(finalize_prompt, inputs=feedback, outputs=result_box)

app.launch()








