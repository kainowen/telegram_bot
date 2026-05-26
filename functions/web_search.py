from langchain_community.tools import DuckDuckGoSearchRun
from duckduckgo_search import DDGS
from telegram import Update
from telegram.ext import ContextTypes

# Create the search tool
search = DuckDuckGoSearchRun()

# Use it in your bot
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Searches DuckDuckGo for search Term"""
    print("Starting: search_command...")
    query = " ".join(context.args)

    if not query:
        await update.message.reply_text("🔍 Please provide a search query!\nExample: /search latest AI news")
        return
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        # Perform search - returns formatted text results
        results = search.invoke(query)
        
        # Telegram has a 4096 character limit per message
        if len(results) > 4000:
            results = results[:4000] + "...\n\n(Results truncated)"
        
        await update.message.reply_text(f"🔍 Search results for: {query}\n\n{results}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Search failed: {str(e)}")


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search for recent news articles"""
    print("Starting: news_command...")
    query = " ".join(context.args)
    
    if not query:
        #await update.message.reply_text("📰 Usage: /news your topic")
        query = "UK Headlines"
        #return
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        import asyncio
        results = await asyncio.to_thread(
            lambda: list(DDGS().news(query, max_results=5))
        )
        
        if not results:
            await update.message.reply_text("No news found.")
            return
        
        news_items = []
        for i, article in enumerate(results, 1):
            title = article.get('title', 'No title')
            date = article.get('date', 'Date unknown')
            body = article.get('body', '')[:150]
            url = article.get('url', '#')
            
            news_items.append(
                f"{i}. {title}\n"
                f"📅 {date}\n"
                f"{body}...\n"
                f"[Read more]({url})\n"
            )
        
        response = f"📰 News about: {query}\n\n" + "\n".join(news_items)
        
        if len(response) > 4000:
            response = response[:4000] + "..."
        
        await update.message.reply_text(response, parse_mode="Markdown")
        
    except Exception as e:
        await update.message.reply_text(f"❌ News search error: {str(e)}")