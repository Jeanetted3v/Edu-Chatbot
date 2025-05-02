"""To run
python -m src.creator.gradio_frontend
Open: http://127.0.0.1:7860
"""
import os
import json
import glob
from pathlib import Path
import gradio as gr
import asyncio
import shutil
import logging

from src.backend.utils.logging import setup_logging
from src.backend.evaluation.simulator_no_db import ChatBotSimulator
from src.creator.chatbot_creator import ChatbotCreator
from src.creator.utils import state as app_state
from src.creator.utils import load_config


cfg = load_config()
logger = logging.getLogger(__name__)
setup_logging()

# Initialize state
creator = ChatbotCreator(cfg)


# Utility wrapper for async
def run_async(coro):
    return asyncio.run(coro)


# ---------Screen 1: File Upload & Model Selection------------
def upload_file(file):
    if file is None:
        return "⚠️ No file selected."
    
    target = Path(cfg.data_ingest_dir) / file.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(file.name, target)
    return f"✅ File '{file.name}' saved to {target}"


def set_model(model_name):
    cfg.input_doc_agent.model_name = model_name
    app_state["model_name"] = model_name
    return f"Model set to: {model_name}"


def summarize_and_proceed(file):
    if file is None:
        return (
            "⚠️ Please upload a file first.",
            gr.update(visible=False),
            gr.update(visible=True)
        )
    
    # Summarize document
    try:
        summary = run_async(creator.summarize_input_doc())
        app_state["summary"] = summary
        return (
            "✅ Document summarized successfully. Ready to proceed.",
            gr.update(visible=True),
            gr.update(visible=False)
        )
    except Exception as e:
        logger.error(f"Error summarizing document: {e}")
        return (
            f"❌ Error summarizing document: {str(e)}",
            gr.update(visible=False),
            gr.update(visible=True)
        )


# Screen 2: -------Chat Interface for Prompt Creation-------
def create_prompts():
    if not app_state["summary"]:
        return (
            "No summary available. Please go back and summarize the input document first.",
            "",
            ""
        )
    try:
        sim_prompt, chat_prompt = run_async(creator.create_prompt(app_state["summary"]))
        app_state["sim_prompt"] = sim_prompt
        app_state["chat_prompt"] = chat_prompt
        return (
            "✅ Initial prompts created successfully!",
            sim_prompt,
            chat_prompt
        )
    except Exception as e:
        logger.error(f"Error creating prompts: {e}")
        return f"❌ Error creating prompts: {str(e)}", "", ""


# for initial prompt creation only, similatution for prompt optimization is under optimize_prompt
def generate_simulations():
    if not app_state["sim_prompt"]:
        return (
            "No simulation prompt available. Please create prompts first.",
            gr.update(visible=False)
        )
    try:
        # Clear previous conversations
        app_state["conversations"] = []
        app_state["current_conv_index"] = 0
        app_state["feedback_history"] = []
        
        # Run simulations to generate conversations
        simulator = ChatBotSimulator(cfg)
        run_async(simulator.run_simulations(cfg.simulator.num_simulations))

        # Load generated conversation files
        json_files = glob.glob(os.path.join(cfg.simulation_dir, '*.json'))
        for file_path in json_files:
            with open(file_path, 'r') as f:
                conversation = json.load(f)
                app_state["conversations"].append(conversation)
        
        if not app_state["conversations"]:
            return (
                "⚠️ No conversations were generated.",
                gr.update(visible=False)
            )
        
        # Prepare first conversation for review
        return (
            "✅ Generated 10 conversation sets. Ready for feedback!",
            gr.update(visible=True)
        )
    except Exception as e:
        logger.error(f"Error generating simulations: {e}")
        return (
            f"❌ Error generating simulations: {str(e)}",
            gr.update(visible=False)
        )


def prepare_conversation_for_display(index=None):
    if index is not None:
        app_state["current_conv_index"] = index
    
    if not app_state["conversations"] or app_state["current_conv_index"] >= len(app_state["conversations"]):
        return (
            "No conversation to display",
            "",
            "",
            "0/0",
            gr.update(visible=False)
        )
    
    current_conv = app_state["conversations"][app_state["current_conv_index"]]
    
    # Format the conversation for display
    chat_html = ""
    for turn in current_conv:
        chat_html += "<div style='margin-bottom: 15px;'>"
        chat_html += f"<p><strong>User:</strong> {turn['customer_inquiry']}</p>"
        chat_html += f"<p><strong>Bot:</strong> {turn['bot_response']}</p>"
        chat_html += "</div>"
    
    conversation_id = f"Conversation {app_state['current_conv_index'] + 1}/10"
    
    # Determine if we should show next button
    show_next = app_state["current_conv_index"] < len(app_state["conversations"]) - 1
    
    return (
        chat_html,
        "",
        "",
        conversation_id,
        gr.update(visible=show_next)
    )


def submit_feedback(feedback_text):
    if not feedback_text.strip():
        return (
            "⚠️ Please provide feedback before proceeding.",
            gr.update(visible=True)
        )
    current_idx = app_state["current_conv_index"]
    current_conv = app_state["conversations"][current_idx]
    
    # Save feedback
    app_state["feedback_history"].append({
        "conversation_index": current_idx,
        "conversation": current_conv,
        "feedback": feedback_text
    })
    
    # Move to next conversation
    app_state["current_conv_index"] += 1
    
    # Check if we've gone through all conversations
    if app_state["current_conv_index"] >= len(app_state["conversations"]):
        return (
            "✅ All feedback collected! Ready for final decision.",
            gr.update(visible=False, _js="() => { document.getElementById('check_transition').click(); return true; }")
        )
    else:
        return (
            "✅ Feedback submitted! Moving to next conversation.",
            gr.update(visible=True)
        )


def process_all_feedback():
    if len(app_state["feedback_history"]) < len(app_state["conversations"]):
        return (
            "⚠️ Please provide feedback for all conversations first.",
            None,
            None
        )
    # Format feedback for optimizer
    feedback_list = []
    for fb in app_state["feedback_history"]:
        for turn in fb["conversation"]:
            feedback_list.append({
                "customer_inquiry": turn["customer_inquiry"],
                "bot_response": turn["bot_response"],
                "feedback": fb["feedback"]
            })
    
    app_state["regeneration_count"] += 1
    
    return (
        f"✅ All feedback processed! This is regeneration #{app_state['regeneration_count']}.\n"
        "Would you like to regenerate the prompts or deploy the current version?",
        gr.update(visible=True),
        gr.update(visible=True)
    )


def regenerate_prompts():
    try:
        if not app_state.get("summary"):
            return (
                "⚠️ No document summary available. Please go back to step 1.",
                1
            )
        # Use the feedback to optimize prompts
        chat_prompt, sim_prompt, convo_feedback = run_async(
            creator.optimize_prompts()
        )
        app_state["chat_prompt"] = chat_prompt
        app_state["sim_prompt"] = sim_prompt
        
        # Reset for new feedback round
        app_state["conversations"] = []
        app_state["current_conv_index"] = 0
        app_state["feedback_history"] = []

        # Load the generated conversation files (don't regenerate them)
        json_files = glob.glob(os.path.join(cfg.simulation_dir, '*.json'))
        for file_path in json_files:
            with open(file_path, 'r') as f:
                conversation = json.load(f)
                app_state["conversations"].append(conversation)
        
        if not app_state["conversations"]:
            return (
                "⚠️ No conversations were generated during optimization.",
                1
            )
        return (
            "🔄 Prompts regenerated and new conversations created. Ready for feedback!",
            3
        )
    except Exception as e:
        logger.error(f"Error regenerating prompts: {e}")
        return f"❌ Error regenerating prompts: {str(e)}", 1
    

def deploy_prompts():
    try:
        # Save final prompts
        creator.update_prompt_files(app_state["sim_prompt"], app_state["chat_prompt"])
        return "🚀 Deployment in progress! Your chatbot prompts are being deployed.", 3
    except Exception as e:
        logger.error(f"Error deploying prompts: {e}")
        return f"❌ Error deploying prompts: {str(e)}", 1


# ---------Gradio App Setup------------
# Main Gradio App
with gr.Blocks(title="🤖 Interactive Prompt Creator") as app:
    # Application state (hidden)
    current_screen = gr.State(value=1)
    
    # Screen 1: File Upload & Model Selection
    with gr.Group(visible=True) as screen1:
        gr.Markdown("# 📁 Step 1: Upload Files & Select Model")
        
        with gr.Row():
            file_upload = gr.File(label="Upload Input Documents (txt, pdf, etc.)")
            upload_msg = gr.Textbox(label="Status", interactive=False)
        
        with gr.Row():
            model_dropdown = gr.Dropdown(
                choices=["gpt-4o-mini", "gpt-4.1-mini"],
                value=app_state["model_name"],
                label="Select LLM Model"
            )
            model_status = gr.Textbox(label="Model Status", interactive=False)
        
        with gr.Row():
            summarize_btn = gr.Button("📝 Summarize & Embed Documents")
            summary_status = gr.Textbox(label="Summary Status", interactive=False)
        
        with gr.Row():
            next_to_screen2 = gr.Button("▶️ Next: Create Prompts", visible=False)
    
    # Screen 2: Chat Interface for Prompt Creation
    with gr.Group(visible=False) as screen2:
        gr.Markdown("# 💬 Step 2: Create & Test Prompts")
        
        with gr.Row():
            gr.Markdown("### Create initial prompts for your simulator and chatbot")
        
        with gr.Row():
            create_prompts_btn = gr.Button("✨ Create Initial Prompts")
            prompt_status = gr.Textbox(label="Prompt Creation Status", interactive=False)
        
        with gr.Row():
            sim_prompt_box = gr.Textbox(label="Simulator Prompt", lines=8)
            chat_prompt_box = gr.Textbox(label="Chatbot Response Prompt", lines=8)
        
        with gr.Row():
            generate_sims_btn = gr.Button("🔄 Generate Test Conversations")
            sim_status = gr.Textbox(label="Simulation Status", interactive=False)
        
        with gr.Row():
            next_to_screen3 = gr.Button("▶️ Next: Review Conversations", visible=False)
    
    # Screen 3: Conversation Review & Feedback
    with gr.Group(visible=False) as screen3:
        gr.Markdown("# 🔍 Step 3: Review Conversations & Provide Feedback")
        
        with gr.Row():
            conversation_id = gr.Textbox(label="", interactive=False)
        
        with gr.Row():
            conversation_display = gr.HTML(label="Conversation")
        
        with gr.Row():
            feedback_input = gr.Textbox(
                label="Your Feedback", 
                placeholder="Provide detailed feedback on this conversation...",
                lines=4
            )
        
        with gr.Row():
            submit_feedback_btn = gr.Button("Submit Feedback")
            feedback_status = gr.Textbox(label="Status", interactive=False)
        
        with gr.Row():
            next_conversation_btn = gr.Button("▶️ Next Conversation", visible=True)
    
    # Screen 4: Final Decision
    with gr.Group(visible=False) as screen4:
        gr.Markdown("# 🏁 Step 4: Final Decision")
        
        with gr.Row():
            decision_status = gr.Textbox(label="Status", interactive=False)
        
        with gr.Row():
            regenerate_btn = gr.Button("🔄 Regenerate Prompts", visible=False)
            deploy_btn = gr.Button("🚀 Deploy Prompts", visible=False)
    
    # Screen 5: Deployment
    with gr.Group(visible=False) as screen5:
        gr.Markdown("# 🚀 Deployment")
        
        with gr.Row():
            gr.HTML("""
                <div style="text-align: center; padding: 50px;">
                    <h1 style="font-size: 72px;">🚀</h1>
                    <h2>Deploying Your Chatbot</h2>
                    <p>Your optimized prompts are being deployed. This may take a few moments.</p>
                </div>
            """)
        
        with gr.Row():
            deployment_status = gr.Textbox(label="Deployment Status", interactive=False)
    
    # --- Event Handlers ---
    
    # Screen 1 Events: File upload and model selection
    file_upload.change(upload_file, inputs=file_upload, outputs=upload_msg)
    model_dropdown.change(set_model, inputs=model_dropdown, outputs=model_status)
    summarize_btn.click(
        summarize_and_proceed, 
        inputs=[file_upload], 
        outputs=[summary_status, next_to_screen2, summarize_btn]
    )
    next_to_screen2.click(
        lambda: (2, gr.update(visible=False), gr.update(visible=True)),
        outputs=[current_screen, screen1, screen2]
    )
    
    # Screen 2 Events: Create prompts, then generate simulations
    create_prompts_btn.click(
        create_prompts,
        outputs=[prompt_status, sim_prompt_box, chat_prompt_box]
    )
    generate_sims_btn.click(
        generate_simulations,
        outputs=[sim_status, next_to_screen3]
    )
    next_to_screen3.click(
        lambda: (3, gr.update(visible=False), gr.update(visible=True), *prepare_conversation_for_display()),
        outputs=[current_screen, screen2, screen3, conversation_display, feedback_input, feedback_status, conversation_id, next_conversation_btn]
    )
    
    # Screen 3 Events: Go through conversations and submit feedback
    submit_feedback_btn.click(
        submit_feedback,
        inputs=[feedback_input],
        outputs=[feedback_status, next_conversation_btn]
    )
    next_conversation_btn.click(
        lambda: prepare_conversation_for_display(),
        outputs=[conversation_display, feedback_input, feedback_status, conversation_id, next_conversation_btn]
    )
    # Add a separate check button (hidden) that's triggered programmatically
    check_transition = gr.Button(visible=False, elem_id="check_transition")
    check_transition.click(
        lambda: (4, gr.update(visible=False), gr.update(visible=True), *process_all_feedback()) 
        if app_state["current_conv_index"] >= len(app_state["conversations"])
        else (None, None, None, None, None, None),
        outputs=[current_screen, screen3, screen4, decision_status, regenerate_btn, deploy_btn]
    )
    
    # Screen 4 Events: Regenerate or Deploy
    # Split the chained events
    regenerate_result = regenerate_btn.click(
        regenerate_prompts,
        outputs=[decision_status, current_screen]
    )

    # Add separate handlers instead of chaining
    regenerate_result.then(
        lambda x: (gr.update(visible=False), gr.update(visible=True)) if x == 3 else (None, None),
        inputs=[current_screen],
        outputs=[screen4, screen3]
    )

    # Add this as a separate handler
    regenerate_result.then(
        lambda: prepare_conversation_for_display(0),
        outputs=[conversation_display, feedback_input, feedback_status, conversation_id, next_conversation_btn]
    )
    
    deploy_btn.click(
        deploy_prompts,
        outputs=[deployment_status, current_screen]
    ).then(
        lambda x: (gr.update(visible=False), gr.update(visible=True)) if x == 3 else (None, None),
        inputs=[current_screen],
        outputs=[screen4, screen5]
    )

# Launch the app
app.launch()