import os
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


# ================= GENERATE CODE =================

async def code(update, context, OLLAMA_BASE_URL, TARGET_MODEL):
    """Generates a section of code based on a request in telegram and writes it to a tool.py file."""
    user_message = update.message.text.replace("/code","")
    user_id = str(update.effective_user.id)
    chat_id = update.effective_chat.id
    SYSTEM_PROMPT = "You are a Python script generator. Your goal is to provide functional, concise code based on user requests.\
                    STRICT RULES:\
                    Output ONLY valid Python code.\
                    Do NOT use Markdown formatting (no ```python blocks).\
                    Do NOT provide explanations, greetings, or commentary.\
                    Ensure the code is self-contained and runnable."

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
    try:
       # Initialize LLM
        llm = ChatOllama(
            base_url=OLLAMA_BASE_URL,
            model=TARGET_MODEL,
            temperature=0.7,
        )
        
        
        # Create ChatPromptTemplate
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("user", "{input}")  # This tells LangChain where to inject user_message
        ])
        
        # Create chain
        chain = ( prompt 
                | llm 
                | StrOutputParser()
                )


        # Invoke with the user's code request
        bot_reply = chain.invoke(
            {"input": user_message},
            config={"configurable": {"session_id": user_id}}
            )

        #Write code to temp tool.py file
        tool_path = "temp_utilities/tool.py"
        if os.path.exists(tool_path):
            with open(tool_path, "w") as file:
                file.write(bot_reply)

        await update.message.reply_text(f"Code succesfuly writen to /temp_utilities/tool.py")

            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")