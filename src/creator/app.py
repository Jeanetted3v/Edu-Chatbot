"""To run:
python -m src.creator.app
Open: http://127.0.0.1:7860
To run auto reload:
gradio app.py
Need to import modules with absolute path
and cd into src/creator directory 
"""
import sys
import os
from pathlib import Path
import gradio as gr
import asyncio
import shutil
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.backend.utils.logging import setup_logging
from src.creator.chatbot_creator import ChatbotCreator
from src.creator.utils import state as app_state
from src.creator.utils import load_config


cfg = load_config()
logger = logging.getLogger(__name__)
setup_logging()

# Initialize state
creator = ChatbotCreator(cfg)
if "mode" not in app_state:
    app_state["mode"] = cfg.creator.mode


# Utility wrapper for async
def run_async(coro):
    return asyncio.run(coro)


def toggle_mode():
    """Toggle between create and optimize modes."""
    current_mode = cfg.creator.mode
    new_mode = "optimize" if current_mode == "create" else "create"
    
    # Update both app_state and config
    app_state["mode"] = new_mode
    cfg.creator.mode = new_mode
    
    logger.info(f"🔄 Switched to {new_mode} mode")
    # Return updated UI elements - fixed to avoid "label" attribute
    next_text = "▶️ Next: Review Prompts" if new_mode == "optimize" else "▶️ Next: Create Prompts"
    # Return updated UI elements
    return (
        f"Current Mode: {new_mode.upper()}",
        gr.update(visible=new_mode == "optimize"),
        next_text
    )


# ---------Screen 1: File Upload & Model Selection------------
def upload_file(file):
    if file is None:
        return "⚠️ No file selected."
    filename = os.path.basename(file.name)
    target = Path(cfg.creator.data_ingest_dir) / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(file.name, target)
    return f"✅ File '{filename}' saved to {target}"


def set_model(model_name):
    cfg.creator.input_doc_agent.model_name = model_name
    app_state["model_name"] = model_name
    logger.info(f"Model set to: {model_name}")
    return f"Model set to: {model_name}"


def summarize_and_proceed(file):
    if file is None:
        return (
            "⚠️ Please upload a file first.",
            gr.update(visible=False),
            gr.update(visible=True)
        )
    try:
        summary = run_async(creator.summarize_input_doc())
        app_state["summary"] = summary
        # In optimize mode, check if we need to load prompts
        if cfg.creator.mode == "optimize":
            logger.info("Optimize mode detected, prompts will be loaded in the next step")
        return (
            "✅ Document summarized successfully. Ready to proceed.",
            gr.update(visible=True)
        )
    except Exception as e:
        logger.error(f"Error summarizing document: {e}")
        return (
            f"❌ Error summarizing document: {str(e)}",
            gr.update(visible=False)
        )


def load_existing_prompts():
    try:
        # Check if we have a document summary
        if not app_state.get("summary"):
            return (
                "⚠️ Please upload and summarize a document first.",
                gr.update(visible=False)
            )
        
        sim_prompt, chat_prompt, reasoning_prompt = run_async(creator.create_prompt())
        app_state["sim_prompt"] = sim_prompt
        app_state["chat_prompt"] = chat_prompt
        app_state["reasoning_prompt"] = reasoning_prompt
        return (
            "✅ Loaded existing prompts. Ready to proceed.",
            gr.update(visible=True)
        )
    except Exception as e:
        logger.error(f"Error loading existing prompts: {e}")
        return (
            f"❌ Error loading existing prompts: {str(e)}",
            gr.update(visible=False)
        )


# Screen 2: -------Chat Interface for Prompt Creation-------

# Function to handle chat submissions
def handle_chat_message(message, history):
    """Process a chat message and update prompts if complete."""
    if not message:
        return "", history, "", "", gr.update(visible=False), ""
    
    try:
        assistant_response, updated_history, is_complete, sim_prompt, chat_prompt = run_async(
            creator.create_prompt(message, history)
        )
        if is_complete:
            # Update app_state
            app_state["prompt_creation_complete"] = True
            
            return (
                "", 
                updated_history, 
                sim_prompt or app_state.get("sim_prompt", ""), 
                chat_prompt or app_state.get("chat_prompt", ""), 
                gr.update(visible=True),
                "✅ Prompts created successfully!"
            )
        # If not complete, just update chat
        return "", updated_history, "", "", gr.update(visible=False), ""
        
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        return "", history, "", "", gr.update(visible=False), f"❌ Error: {str(e)}"


def check_prompt_completion():
    """Check if prompts are complete and update UI accordingly."""
    is_complete = app_state.get("prompt_creation_complete", False)
    
    if is_complete:
        sim_prompt = app_state.get("sim_prompt", "")
        chat_prompt = app_state.get("chat_prompt", "")
        
        return (
            sim_prompt,
            chat_prompt,
            "✅ Prompts created successfully!",
            gr.update(visible=True)  # Show next button
        )
    else:
        return (
            sim_prompt_box.value,  # Maintain current values
            chat_prompt_box.value,
            "",
            gr.update(visible=False)
        )
    

def generate_simulations():
    try:
        # Clear previous conversations
        app_state["conversations"] = []
        app_state["current_conv_index"] = 0
        app_state["feedback_history"] = []
        
        # Generate conversations using the dedicated backend function
        conversations = run_async(creator.generate_simulations())
        app_state["conversations"] = conversations

        if not app_state["conversations"]:
            return (
                "⚠️ No conversations were generated.",
                gr.update(visible=False)
            )
        return (
            f"✅ Generated {len(conversations)} conversation sets. Ready for feedback!",
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
        # Check if we have collected feedback for all conversations
        if len(app_state.get("feedback_history", [])) < len(app_state.get("conversations", [])):
            return (
                "⚠️ Please provide feedback for all conversations first.",
                1
            )
        # Use the feedback to optimize prompts, which include simulation
        chat_prompt, sim_prompt = run_async(
            creator.optimize_prompts()
        )
        app_state["chat_prompt"] = chat_prompt
        app_state["sim_prompt"] = sim_prompt
        
        # Reset for new feedback round
        app_state["conversations"] = []
        app_state["current_conv_index"] = 0
        app_state["feedback_history"] = []

        # Generate new simulations with the optimized prompts
        conversations = run_async(creator.generate_simulations())
        app_state["conversations"] = conversations
        
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
        creator.update_prompt_files(
            app_state["sim_prompt"],
            app_state["chat_prompt"],
            app_state["reasoning_prompt"]
        )
        return "🚀 Deployment in progress! Your chatbot prompts are being deployed.", 3
    except Exception as e:
        logger.error(f"Error deploying prompts: {e}")
        return f"❌ Error deploying prompts: {str(e)}", 1


def handle_screen_transition_after_regenerate(new_screen):
    if new_screen == 3:
        return gr.update(visible=False), gr.update(visible=True)
    return None, None


def handle_conversation_display_after_regenerate():
    return prepare_conversation_for_display(0)


# ---------Gradio App Setup------------
# Main Gradio App
with gr.Blocks(title="🤖 Interactive Prompt Creator") as demo:
    # Application state (hidden)
    current_screen = gr.State(value=1)
    # Screen 1: Initial Setup with Mode Toggle
    with gr.Group(visible=True) as screen1:
        gr.Markdown("# 📁 Step 1: Initial Setup")
        
        with gr.Row():
            mode_display = gr.HTML(f"<div><h3>Current Mode: {cfg.creator.mode.upper()}</h3></div>")
            mode_toggle = gr.Button("🔄 Toggle Mode")

        # Document upload and summarization (needed for both modes)
        with gr.Group() as doc_upload_group:
            gr.Markdown("## Upload Files & Select Model")
            with gr.Row():
                file_upload = gr.File(label="Upload Input Documents (txt, pdf, etc.)")
                upload_msg = gr.Textbox(label="Status", interactive=False)
            with gr.Row():
                model_dropdown = gr.Dropdown(
                    choices=["gpt-4o-mini", "gpt-4.1-mini"],
                    value=app_state.get("model_name", "gpt-4o-mini"),
                    label="Select LLM Model"
                )
                model_status = gr.Textbox(label="Model Status", interactive=False)
        
            with gr.Row():
                summarize_btn = gr.Button("📝 Summarize & Embed Documents")
                summary_status = gr.Textbox(label="Summary Status", interactive=False)
        
        # Optimize mode load prompts button
        with gr.Group(visible=cfg.creator.mode == "optimize") as optimize_group:
            with gr.Row():
                load_prompts_btn = gr.Button("🔄 Load Existing Prompts")
                load_status = gr.Textbox(label="Load Status", interactive=False)

        with gr.Row():
            next_btn_text = f"▶️ Next: {'Create Prompts' if cfg.creator.mode == 'create' else 'Review Prompts'}"
            next_to_screen2 = gr.Button(next_btn_text, visible=False)

    # Screen 2: Chat Interface for Prompt Creation
    with gr.Group(visible=False) as screen2:
        gr.Markdown("# 💬 Step 2: Create & Test Prompts")
        
        with gr.Row():
            gr.Markdown("### Talk with the Meta Prompt Creator to build your chatbot")
        
        # Create a manual chat interface instead of using ChatInterface
        chat_history = gr.Chatbot(height=400, label="Conversation with Meta Prompt Creator")
        
        with gr.Row():
            user_input = gr.Textbox(
                placeholder="Describe what you want your chatbot to do...", 
                label="Your Message",
                lines=3
            )
            chat_submit_btn = gr.Button("Send")
        
        with gr.Row():
            gr.Markdown("### Examples:")
            example1_btn = gr.Button("I need a chatbot for customer support")
            example2_btn = gr.Button("I want a chatbot for IT troubleshooting")
            example3_btn = gr.Button("I need a sales chatbot")
        
        with gr.Row():
            prompt_status = gr.Textbox(label="Status", interactive=False)
        
        # Prompt display and editing
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
    # Mode toggle handler
    mode_toggle.click(
        toggle_mode,
        outputs=[mode_display, optimize_group, next_to_screen2]
    )
    
    # Screen 1 Events: File upload and model selection
    file_upload.change(upload_file, inputs=file_upload, outputs=upload_msg)
    model_dropdown.change(set_model, inputs=model_dropdown, outputs=model_status)
    summarize_btn.click(
        summarize_and_proceed, 
        inputs=[file_upload], 
        outputs=[summary_status, next_to_screen2]
    )

    # Load existing prompts button (only shown in optimize mode)
    load_prompts_btn.click(
        load_existing_prompts,
        outputs=[load_status, next_to_screen2]
    )
    next_to_screen2.click(
        lambda: (2, gr.update(visible=False), gr.update(visible=True)),
        outputs=[current_screen, screen1, screen2]
    )
    
    # Screen 2 Events: Create prompts, then generate simulations
    chat_submit_btn.click(
        handle_chat_message,
        inputs=[user_input, chat_history],
        outputs=[user_input, chat_history, sim_prompt_box, chat_prompt_box, 
                 next_to_screen3, prompt_status]
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
    # Fix: Use separate event handlers instead of chaining .then()
    regenerate_btn.click(
        regenerate_prompts,
        outputs=[decision_status, current_screen]
    )
    # Add transition event handler
    current_screen.change(
        handle_screen_transition_after_regenerate,
        inputs=[current_screen],
        outputs=[screen4, screen3]
    )
    # Handle refreshing the conversation display when returning to screen 3
    current_screen.change(
        lambda x: handle_conversation_display_after_regenerate() if x == 3 else (None, None, None, None, None),
        inputs=[current_screen],
        outputs=[conversation_display, feedback_input, feedback_status, conversation_id, next_conversation_btn]
    )
    
    # Deploy button handling
    deploy_btn.click(
        deploy_prompts,
        outputs=[deployment_status, current_screen]
    )
    # Handle transition to deployment screen
    current_screen.change(
        lambda x: (gr.update(visible=False), gr.update(visible=True)) if x == 5 else (None, None),
        inputs=[current_screen],
        outputs=[screen4, screen5]
    )

# Initialize "regeneration_count" if it doesn't exist
if "regeneration_count" not in app_state:
    app_state["regeneration_count"] = 0

# Launch the app
demo.launch()