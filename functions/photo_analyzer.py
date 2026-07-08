import base64
import asyncio
from io import BytesIO
from telegram import Update
from telegram.ext import ContextTypes
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from PIL import Image
from functions import projectMemory


async def analyze_image(update: Update, context: ContextTypes.DEFAULT_TYPE, OLLAMA_BASE_URL, SYSTEM_PROMPT,TARGET_MODEL,DATABASE_URL,user_memories,PERSONALITY):
    """Analyze photos using LangChain + Gemma 4 E4B."""
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
        # Download the image from Telegram
        file = await context.bot.get_file(photo.file_id)
        image_data = BytesIO()
        await file.download_to_memory(image_data)
        image_data.seek(0)
        
        # Resizes the image for data management
        img = Image.open(image_data)

        #Get original size for logging
        original_size = image_data.getbuffer().nbytes / 1024 #kb

         # Resize to a reasonable dimension (max 768px on longest side)
        max_dimension = 720
        if max(img.size) > max_dimension:
            ratio = max_dimension / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)  # High-quality downsampling
        
        # Convert to RGB if necessary (handles PNG with transparency)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # Save to BytesIO with compression
        resized_data = BytesIO()
        img.save(resized_data, format='JPEG', quality=85, optimize=True)
        resized_data.seek(0)
        
        new_size_kb = resized_data.getbuffer().nbytes / 1024
        print(f"Resized image size: {new_size_kb:.1f} KB, dimensions: {img.size}")

        # Convert to base64 and create the data URL
        base64_image = base64.b64encode(resized_data.getvalue()).decode('utf-8')
        image_url = f"data:image/jpeg;base64,{base64_image}"


        #
        # Initialize the LLM with Gemma 4
        llm = ChatOllama(
            base_url=OLLAMA_BASE_URL,  # Your existing config
            model=TARGET_MODEL,
            temperature=0.3,
            num_predict=512,
            reasoning=False
        )
        # Get memory for this user
        user_mem = projectMemory.get_session_history(session_id=str(update.effective_user.id),DATABASE_URL=DATABASE_URL,personality=PERSONALITY)

        # Create the message with both text and image
        # Get past context
        history_context = user_mem.messages
        
        # Build message list
        message = [HumanMessage(content=str(history_context))] # Add history
        
        # Add the new request (keep the image here for the LLM to see)
        message.append(HumanMessage(content=[
            {"type": "text", "text": f"SYSTEM PROMPT: {SYSTEM_PROMPT}"},
            {"type": "text", "text": f"User question: {user_question}"},
            {"type": "image_url", "image_url":image_url}
        ]))

        # Invoke the model
        response = await asyncio.to_thread(llm.invoke, message)
        
        # Delete processing message and send the response
        await processing_msg.delete()
        await update.message.reply_text(f"📷 Photo Analysis:\n\n{response.content}")
        
        # Save a text-only representation to the SQL store
        memoryOBJ =projectMemory.SQLBackedSummaryMemory(user_id, DATABASE_URL,personality=PERSONALITY,llm=llm)
        memoryOBJ.save_context(
            {"input":f"[Photo Analysis Request]: {user_question}"},
            {"output":response.content}
        )

    except asyncio.TimeoutError:
        await processing_msg.edit_text("⏰ Analysis took too long. Please try again with a smaller image.")
    except Exception as e:
        await processing_msg.edit_text(f"❌ Error analyzing plant: {str(e)}")