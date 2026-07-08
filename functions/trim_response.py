import re
import operator as op
import json
import markdown

TestString =  ("""Hey! This sounds like an awesome, genuinely decentralized project. Building something powerful like this locally—keeping the intelligence on your own hardware—is exactly how we build true digital autonomy and escape the proprietary chokehold of massive tech corporations. Love the stack choice; it's solid, flexible, and entirely open-source.

Since you want a detailed roadmap and README structure, I’ve broken this down into two parts: the Development Roadmap (how to build it) and the Project README Skeleton (the necessary documentation).

## Project Roadmap: Local AI Dev Assistant
We need to approach this modularly. Think of each component as a self-contained worker that contributes to the collective goal, rather than one massive monolith.

### Phase 0: Environment & Setup Foundation
Goal: Get all pieces talking to each other locally without headaches.
Tasks:
Virtual Environment: Set up venv or Conda for isolation. Never install these dependencies globally!
Ollama Service: Ensure Ollama is running and Qwen2.5-Coder:7b is pulled (ollama pull qwen2.5-coder:7b). Test basic API calls against it (e.g., using requests in a simple Python script) to confirm connectivity.
Basic Flask App: Create the bare minimum app.py with one single test route (/health) that returns "System Online."
###Phase 1: The Core Intelligence Layer (Backend Logic)
Goal: Implement the brain—the LangGraph agent that coordinates the LLM calls, tool usage, and context memory.
Tasks:
Tool Definition: Define a set of "tools" your assistant can use (e.g., search_local_files(filename), run_python_code(code)). These tools are critical for making the agent useful beyond just chatting.
LangChain Integration: Wrap the Ollama client call within Langchain's structure, ensuring it correctly passes system prompts and context history.
LangGraph State Machine: This is where complexity lives. Build a graph that dictates the flow: Input -> Agent Call -> Tool Check -> Execute Tool -> Output/Final Answer. The state must manage conversation memory effectively to avoid losing context.
API Endpoint Integration: Create the main backend endpoint (e.g., /api/query) in Flask. This function will receive user input from the frontend, pass it to the LangGraph engine, and return the structured response.
###Phase 2: The Presentation Layer (Frontend)
Goal: Build a usable interface that communicates with the backend API gracefully.
Tasks:
Basic HTML/CSS Structure: Create a simple single-page application (index.html). Needs a clear input area, and a dedicated output panel for streaming results.
JavaScript Logic: Use vanilla JavaScript (or a minimal framework like HTMX if you prefer) to handle user input. Crucially, use the fetch API to communicate with your Flask /api/query endpoint.
Streaming UX: Modify the JS to stream the response from the server. Instead of waiting for the whole answer, it should display chunks as they arrive—this makes the experience feel fast and responsive.
###Phase 3: Polish, Persistence & Deployment
Goal: Make it robust, resilient, and shareable.
Tasks:
Error Handling: Implement detailed try...except blocks across Flask and LangGraph to catch API failures, model timeouts, and tool execution errors, providing helpful feedback to the user instead of crashing.
Context Persistence (Optional but recommended): Implement a local database (SQLite is perfect) to save conversation history so the assistant remembers multi-session context.
Containerization: Write a Dockerfile and potentially docker-compose.yml. This allows anyone—or just you—to spin up the entire system (Flask + Ollama setup if desired) with one command, ensuring true reproducibility.

###Project README Skeleton
A great project needs excellent documentation. Use this structure for your main README.md. I've included notes to guide your tone and contribution model.

markdown


# Local Code Assistant: [Your Project Name]

## Overview & Philosophy
*Briefly explain what it is, but focus on the *why*. This is where you emphasize local control.*

[Project Name] is a powerful, open-source coding assistant designed to run entirely locally. It leverages the efficiency of smaller, state-of-the-art models (like Qwen2.5) running via Ollama, ensuring that all computational power and data remain under your direct digital sovereignty. We are building an alternative to proprietary cloud AI services.

## Tech Stack
*List everything used. This is crucial for contributors.*

*   **Backend Logic:** LangChain, LangGraph, Python
*   **API Framework:** Flask (Minimalist web server)
*   **Model Engine:** Ollama
*   **AI Model:** Qwen2.5-Coder:7b
*   **Frontend:** HTML/CSS/JavaScript

## Getting Started
*Make this section as foolproof as possible.*

### Prerequisites
You must have the following installed and running before attempting to run the app:
1.  Docker (Recommended for deployment) or Python 3.10+.
2.  Ollama Service: Ensure Ollama is running in the background, and pull the required model: `ollama pull qwen2.5-coder:7b`

### Installation
```bash
# Clone the repository
git clone [repo-url]
cd [project-name]

# 1. Setup Virtual Environment (Always do this!)
python -m venv venv
source venv/bin/activate  # or .\venv\Scripts\activate for Windows

# 2. Install Dependencies
pip install -r requirements.txt # List all your pip dependencies here!
Running the Application
bash


# Start the Flask server (assuming it's configured to use the local API)
flask run
The assistant should now be accessible at http://localhost:5000.

Usage Guide
Walk the user through what they can and cannot do.

Basic Query: Type a question (e.g., "Write a simple function to reverse a string in Python.") and hit send. The agent will use its internal knowledge and display the code.
Multi-Step Reasoning: Because we use LangGraph, complex tasks are possible. Try: "First, write a class for a book inventory system. Second, add a method that calculates the total value of all books." (This tests context memory).
Architecture Deep Dive (Optional Diagram)
Include a simple diagram showing data flow:
User Input -> Frontend JS -> Flask API -> LangGraph State Machine -> Ollama/Qwen Model -> Output Stream

Contributing & Community Effort
This is the most important part for maintaining an open, decentralized ethos.

We believe that true progress only happens through collective effort. If you find a bug, want to add a new tool (like connecting to a local database or calling a specific API), or just want to improve documentation, please contribute!

Fork the repository.
Create a new branch (git checkout -b feature/amazing-new-tool).
Commit your changes and open a Pull Request (PR).
Let's build this together and keep the intelligence decentralized!




Done — the string has been converted to plain text with all unicode escapes decoded and formatting preserved.""")


class trim_response:

    def __init__(self,max_chars=4000,split_char="### "):
        self.max_chars = max_chars
        self.split_char = split_char
        self.re_split_char = "(" + split_char + ")"

    def trim(self, response):
        """"This function is responsible for spliting the bot response into smaller chunks\
              so that they don't exceed Telegrams 4k char limit."""
            
      #  if op.contains(response, "```"):
       #     matches = re.findall(r'```.*```', response)
        #    print(matches)


        if len(response) > self.max_chars:
            chunks =  re.split(self.re_split_char,response) 
            out = []
            merge_next = False
            for ch in chunks:

                if merge_next:
                    out.append(self.split_char + ch)
                    merge_next = False
                elif ch == self.split_char:
                    merge_next = True
                else:
                    out.append(ch)

            chunks = out
            return chunks

        else: 
            return [response]
    

trimmer = trim_response()
print_text = trimmer.trim(TestString)

#for message in print_text:
#    print(message)
#    print("\n\n")