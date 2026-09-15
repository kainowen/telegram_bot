import base64
import asyncio
from io import BytesIO
from telegram import Update
from telegram.ext import ContextTypes
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from PIL import Image
from functions import projectMemory # Ensure this module is available


async def analyze_image(update: Update, context: ContextTypes.DEFAULT_TYPE, OLLAMA_BASE_URL, SYSTEM_PROMPT, TARGET_MODEL, DATABASE_URL, user_memories, PERSONALITY):
    """Analyze photos."""
    print("Starting: analyse_image")

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Get the highest resolution photo
    photo = update.message.photo[-1]
    
    # Get user's question (caption becomes the text prompt)
    user_question = update.message.caption or "Analyse this photo..."
    
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    # Send a processing message since this takes time
    processing_msg = await update.message.reply_text("📷 Analyzing your photo... This may take 20-30 seconds.")
    
    try:
        # --- IMAGE PROCESSING STAGE (Identical) ---
        file = await context.bot.get_file(photo.file_id)
        image_data = BytesIO()
        await file.download_to_memory(image_data)
        image_data.seek(0)
        
        img = Image.open(image_data)

        original_size = image_data.getbuffer().nbytes / 1024
        
        max_dimension = 720
        if max(img.size) > max_dimension:
            ratio = max_dimension / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        resized_data = BytesIO()
        img.save(resized_data, format='JPEG', quality=85, optimize=True)
        resized_data.seek(0)
        
        new_size_kb = resized_data.getbuffer().nbytes / 1024
        print(f"Resized image size: {new_size_kb:.1f} KB, dimensions: {img.size}")

        base64_image = base64.b64encode(resized_data.getvalue()).decode('utf-8')
        image_url = f"data:image/jpeg;base64,{base64_image}"

        # --- LLM EXECUTION STAGE (Optimized) ---
        llm = ChatOllama(
            base_url=OLLAMA_BASE_URL,
            model=TARGET_MODEL,
            temperature=0.3,
            num_predict=512,
            reasoning=False
        )
        
        # Get memory for this user
        user_mem = projectMemory.get_session_history(session_id=str(update.effective_user.id), DATABASE_URL=DATABASE_URL, personality=PERSONALITY)
        history_context = user_mem.messages
        
        # Build message list (System -> History -> User Input)
        message = [SystemMessage(content=SYSTEM_PROMPT)] # FIX 1: Use SystemMessage
        message.extend(list(history_context))
        
        # Add the new request (User Message)
        message.append(HumanMessage(content=[
            # Only include the user question text here
            {"type": "text", "text": f"User question: {user_question}"}, 
            {"type": "image_url", "image_url": {"url": image_url}}
        ]))

        # FIX 2: Use ainvoke if possible, fallback to to_thread
        try:
            print("Try")
            response = await llm.ainvoke(message)
        except AttributeError:
            print("Catch")
            response = await asyncio.to_thread(llm.invoke, message)
        
        # --- CLEANUP AND SAVING STAGE ---
        print(1)
        # Delete processing message and send the response
        await processing_msg.delete()
        await update.message.reply_text(f"📷 Photo Analysis:\n\n{response.content}")
        print(2)
        # FIX 3: Assume save_context takes input/output as positional text arguments.
        # You MUST verify this signature in your projectMemory.py file.
        memoryOBJ = projectMemory.SQLBackedSummaryMemory(user_id, DATABASE_URL, personality=PERSONALITY, llm=llm)
        print(3)
        # We must combine the photo context into the input string for the memory store
        input_summary = f"[Photo Analysis Request]: {user_question}\n(Context includes photo base64 data)"
        print(4)
        memoryOBJ.save_context(
            {"input": input_summary},
            {"output": response.content}
        )
        print(5)
    except asyncio.TimeoutError:
        # IMPROVED ERROR HANDLING: Send a new message instead of editing a potentially deleted one
        await update.message.reply_text("⏰ Analysis took too long. Please try again with a smaller image.")
    except Exception as e:
        # IMPROVED ERROR HANDLING: Send a new message with the error details
        print(f"Caught exception: {e}")
        await update.message.reply_text(f"❌ An unexpected error occurred during analysis: {type(e).__name__}. Details: {str(e)}")

