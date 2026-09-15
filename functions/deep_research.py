import os
import re
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

import requests
from bs4 import BeautifulSoup

from ddgs import DDGS
from langchain_ollama import ChatOllama
from langgraph.graph import START, END, StateGraph, add_messages, MessagesState
from langchain_core.messages import HumanMessage,AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate

load_dotenv(override=True)

OLLAMA_BASE_URL = os.getenv('Ollama_URL')
TARGET_MODEL = os.getenv('TARGET_MODEL')
PROOF_READING_MODEL = os.getenv('PROOF_READ_MODEL')

#For Testin
TARGET_MODE = "gemma4:e2b"

class CustomState(BaseModel):
    """A custom state class for managing state through the deep_research graph"""
    system_prompt: str = Field(default="You are a deep reasearch assistant, tasked with producing a report on a given topic. ")
    initial_query: str = Field(default="")
    search_iteration: int = Field(default=0)
    search_queries: List[str] = Field(default_factory=list)
    results_list: List[Dict[str, Any]] = Field(default_factory=list) # Renamed and updated type
    filtered_results: List[Dict[str, Any]] = Field(default_factory=list) # Renamed and updated type
    sources: str = Field(default="")
    response: str = Field(default="")
    report_review: str = Field(default="")

class DeepResearch:
    def __init__(self):
        self.graph = self._define_graph()
        self.search = DDGS()         # Create the search tool
        self.chat = ChatOllama(
                        base_url=OLLAMA_BASE_URL,
                        model=TARGET_MODEL,
                        temperature=0.7,
                        reasoning=False,
                        num_gpu=0
                    )

 
    # Removed self.search_queries = [] from __init__
    def generate_search_terms(self, state: CustomState) -> dict[str, Any]:
        """Generates Search Terms and returns them as a list to update the state."""
        print("generate_search_terms...")
        
        new_iteration_count = state.search_iteration + 1
        system_prompt = state.system_prompt # Using state variable (fixed previously)

        # [LLM Interaction logic remains the same...]
        prompt = f"""{system_prompt}The following is an initial search query from the user. /{state.initial_query} \
            Your first task is to generate 2 variations of this query that could provide a range of ideas around this topic that may be relevant to the research. Be creative in these variations./
            provide your response ONLY as a semi-colon separated list of search queries. No additional text or explanation should be provided besides the list/
            Example question: Can you help me research the pros and cons of Ollama vs Llama.ccp/
            Example response: Ollama vs llama.cpp performance benchmarks on consumer hardware; VRAM usage efficiency comparing Ollama's abstraction layer to native llama.cpp bindings; API maturity comparison for local LLM deployment: Ollama ecosystem versus custom tooling/
            /
            Query: {state.initial_query}"""
        
        response = self.chat.invoke(prompt).content 
                
        # 1. Split by semicolon and strip whitespace from each term.
        # 2. Filter out any resulting empty strings (e.g., if the LLM outputs 'term;;')
        search_list = [term.strip() for term in response.split(";")]
        final_search_queries = [term for term in search_list if term]

        # CRITICAL CHANGE: Return a list object, matching the CustomState definition
        return {
                "search_queries": final_search_queries, # Update the queries
                "search_iteration": new_iteration_count  # <-- MUST RETURN THE COUNTER HERE
            }
    

    def perform_search(self, state: CustomState) -> dict[str, Any]:
        """Performs search for all terms and aggregates results."""
        print("perform_search...")
        all_results = []
        
        # Read queries from the state object
        terms = state.search_queries

        for term in terms:
            if not term: continue # Skip empty strings
            try:
                # Perform search - returns formatted text results (assumes this is done)
                results = self.search.text(
                    query=term,
                    region="uk-en",
                    max_results=1
                )
                all_results.extend(results)
            except Exception as e:
                print(f"❌ Search failed for '{term}': {str(e)}")
        
        # *** CRITICAL CHANGE: Return the updated list ***
        return {"results_list": all_results}
        

    # pass the slug and title to the model, if it seems relevant then add it to a json object, if not then remove it
    def filter_search_results(self, state: CustomState) -> dict[str, Any]:
        """Assesses relevance of sources gathered and updates results_list."""
        print("filter_search_results...")

        final_sources_list = []
        initial_query = state.initial_query
        accumulated_sources = state.filtered_results
        new_sources = []
        if state.search_iteration == 1:
            search_permissiveness = "critical"
        elif state.search_iteration == 2:
            search_permissiveness = "neurtal"
        else: 
            search_permissiveness = "permissive"

        # The system prompt logic remains the same...
        system_prompt = state.system_prompt + f"""Your role is to assess the relevance of an information source, in answering the initial query, based on the article summary./
        be {search_permissiveness} in the sources you allow through.
        You should only return either a 'Pass' or 'Fail'. Followed by a 1 sentence explanation why."""

        for result in state.results_list:            
            # Formatting must be done carefully here:
            result_template = PromptTemplate.from_template(system_prompt + f"\n\nInitial query: {initial_query} /n Article summary {result['body']}")
            formatted_prompt = result_template.format(query=initial_query, summary=result['body'])

            response = self.chat.invoke(formatted_prompt)
            if "Pass" in response.content:
                new_sources.append(result)
            else:
                print(f"""Article '{result['title']}' not relevant""")
        
        final_sources_list = accumulated_sources + new_sources
        
        # *** CRITICAL CHANGE: Return the updated list ***
        return {"filtered_results": final_sources_list}


    # Once we have the relevant article, read each and summarise the key points.
    def consume_articles(self, state: CustomState) -> dict[str, Any]:
        """Reads relevant articles, consumes them, and updates the sources block."""
        print("consume_articles...")
        new_source_content = ""

        # Read results from the state object
        results = state.results_list 
        print(len(results))
        if len(results) > 0:
            for result in results:
                print("Processing Article: ", result["title"])
                try:
                    response = requests.get(result['href'], timeout=10)
                    response.raise_for_status()  

                    soup = BeautifulSoup(response.text, 'html.parser')
                    text = soup.get_text()

                    system_prompt = state.system_prompt + """You form part of a team of deep researchers generating a report on an input query. /
                        "Your role is to consume each article and to generate a short summary article, focusing on the key points and novel ideas contained within./
                        Your output should be a 3 paragraph digest of the article and a bullet point list of usable quotes, highlighting key or novel information."""

                    result_template = PromptTemplate.from_template(system_prompt + f"\n \nArticle Text: {text}")
                    formatted_prompt = result_template.format(text=text)


                    response = self.chat.invoke(formatted_prompt)
                    new_source_content += f"\n \n#### Below are the sources to use in generating your research from {result['title']}'s article:\n{response.content}"   

                # ... (Exception handling remains the same, but do not return errors here unless necessary for flow control)
                except Exception as e:
                    print(f"Error consuming article {result.get('title', 'unknown')}: {e}")
                    continue # Continue processing other articles if one fails
        else:
            print("No results in results_list, no sources consumed.")


        # *** CRITICAL CHANGE: Return the updated string content ***
        return {"sources": new_source_content}


    # pass the keypoints to generate the initial document
    def generate_draft(self, state: CustomState) -> dict[str, Any]:
        """Generates the initial report draft based on gathered sources."""
        print("generate_draft...")
        query = state.initial_query # Use initial query from state
        sources = state.sources   # Use accumulated sources from state
        report = state.response
        
        try:
            if report == "":
                system_prompt = state.system_prompt + """You form part of a team of deep researchers generating a report on an input query. /
                    "Your role is to generate an initial draft of a report based on the below query and sources: ."""
                result_template = PromptTemplate.from_template(system_prompt + f"\nQuery: {query}\n \n Sources: {sources}")
                formatted_prompt = result_template.format(query=query, sources=sources)
            else: 
                system_prompt = state.system_prompt + """You form part of a team of deep researchers generating a report on an input query. /
                "Your role is to read the attached report, as well as the recommended tweeks, and rewrite the report taking the tweeks into account. /"""
                result_template = PromptTemplate.from_template(system_prompt + f"\nLast draft Report: {report}.")
                formatted_prompt = result_template.format(report=report)


            response = self.chat.invoke(formatted_prompt).content
            
            # *** CRITICAL CHANGE: Return the final response text ***
            return {"response": response}

        except Exception as e:
            print(f"Draft generation failed: {e}")
            return {"response": f"Error generating draft report: {str(e)}"}

    def write_report_file(self, state: CustomState) -> dict[str, Any]:
        """Writes the final report draft to a file."""
        print("write_report_file...")
        # Use state.response here instead of self.response
        report_content = state.response 

        if not report_content:
            return {"error": "No content to write to file."}

        # Clean up filename (using the first line as intended)
        try:
            # 1. Get the first line (the title)
            raw_title = report_content.split("\n")[0].replace(" ", "_")

            # 2. SANITIZE THE TITLE USING REGEX            
            cleaned_title = re.sub(r'[^\w\-]', '', raw_title).strip()  # The regex [^a-z0-9_\-\s]+ matches one or more characters that are NOT letters, numbers, underscore or hyphen.


        except IndexError:
            cleaned_title = "final_report" # Fallback

        # The rest of the file writing logic is fine...
        report_path = str(Path(__file__).resolve().parent.parent / os.getenv('DOCS_DIRECTORY')) + f"/{cleaned_title}.md"
        print(f"Attempting to write report to: {report_path}")
        try:
            with open(report_path, "w") as file:
                file.write(report_content)
            print("✅ Report successfully written.")
            return {"response": f"Report successfully generated and saved. It is located at: {report_path}"}


        except Exception as e:
            print(f"Failed to write report file: {str(e)}")
            return {"error": f"Failed to write report file: {str(e)}"}

    #======= Routing functions go here ========
    def check_sources_list(self, state: CustomState) -> str: # Note: return type is now simply 'str'
        """
        Conditional router that checks if relevant sources were found.
        Returns a string naming the next node based on relevance.
        """
        print("Checking source relevance...")
        
        # Check the length of the filtered results list in the state
        if len(state.filtered_results) > 5:
            print("✅ Relevant sources found! Routing to consume_articles.")
            return "consume_articles" # <-- RETURN A STRING HERE
        else:
            print("❌ No relevant sources found. Looping back to generate search terms.")
            # If empty, guide the graph to loop back and try a new query.
            return "generate_search_terms" # <-- RETURN A STRING HERE

    # pass this text to a second model to proof read and tweek against the initial request
    def proof_read_report(self, state: CustomState) -> str:
        """Reads the report generated with a second model, assesses whether or not it answeres the original question, if not it recommends tweeks."""
        print("Proof reading report draft...")
        
        new_iteration_count = state.search_iteration + 1
        system_prompt = state.system_prompt # Using state variable (fixed previously)

        # [LLM Interaction logic remains the same...]
        prompt = f"""{system_prompt}The following is an initial search query from the user. /{state.initial_query} \
            Your task is to read the below report and assess whether or not it answeres the initial query/
            if it does return "Pass", no other text. /
            if it doesn't answer the initial query well, recommend some tweeks that can be used to improve the report.
            /
            Report: {state.response}"""
        
        proof_read_model = ChatOllama(
                    base_url=OLLAMA_BASE_URL,
                    model=PROOF_READING_MODEL,
                    temperature=0.7,
                    reasoning=False,
                    num_gpu=0
                    )


        report_review = proof_read_model.invoke(prompt).content 
        state.report_review = report_review       

        if "Pass" in report_review:
            return "write_report_file"
        else:
            return "generate_draft"
        

    def _define_graph(self):
        # 1. Initialize the graph (same)
        graph = StateGraph(CustomState)
        
        # 2. Add all nodes (including the new router)
        graph.add_node("generate_search_terms", self.generate_search_terms)
        graph.add_node("perform_search", self.perform_search)
        graph.add_node("filter_search_results", self.filter_search_results)
        graph.add_node("check_sources_list", self.check_sources_list) 
        graph.add_node("consume_articles", self.consume_articles)  
        graph.add_node("generate_draft", self.generate_draft) 
        graph.add_node("proof_read_report", self.proof_read_report) 
        graph.add_node("write_report_file", self.write_report_file)  

        # --- Defining the Flow (Replacing simple add_edge calls) ---
        
        # 1. Start always runs search term generation
        graph.set_entry_point("generate_search_terms")
        
        # Standard linear steps
        graph.add_edge("generate_search_terms", "perform_search")
        graph.add_edge("perform_search", "filter_search_results")
        
        # Instead of add_edge, use add_conditional_edges to route based on function output.
        graph.add_conditional_edges(
            "filter_search_results", 
            self.check_sources_list,   # The router function
            { # This dictionary MUST use the same strings returned by the router!
                "consume_articles": "consume_articles", 
                "generate_search_terms": "generate_search_terms"
            }
        )


        # Define remaining edges (The loopback and final steps)
        graph.add_edge("consume_articles", "generate_draft")   
        #graph.add_edge("generate_draft", "write_report_file")  

        graph.add_conditional_edges(
            "generate_draft", 
            self.proof_read_report,   # The router function
            { # This dictionary MUST use the same strings returned by the router!
                "write_report_file": "write_report_file", 
                "generate_draft": "generate_draft"
            }
        )
      
        graph.add_edge("write_report_file", END)

        return graph.compile() 

    
    def research(self, input_query: str) -> CustomState: 
        """Takes the received input and starts a clean Deep Research cycle."""
        print("Starting deep_research...")

        # 1. Initialize a FRESH state object for this specific run.
        new_state = CustomState(initial_query=input_query)

        # --- THE CRITICAL FIX IS HERE ---
        # 2. Convert the Pydantic state object into a standard Python dictionary (dict).
        state_dict_input = new_state.model_dump() 

        # 3. Pass this pure dictionary to LangGraph's invoke method.
        final_state_dict = self.graph.invoke(state_dict_input) 

        # 4. Re-instantiate the CustomState object from the resulting dictionary
        # This ensures the return type matches your expected output (CustomState).
        return CustomState(**final_state_dict)

if __name__ == "__main__": 
    deep_research_test = DeepResearch()
    deep_research_test.research("Could you reasearch the pros and cons of th most popular sarms (selective androgen modulators) for strength and lean muscle gains?")