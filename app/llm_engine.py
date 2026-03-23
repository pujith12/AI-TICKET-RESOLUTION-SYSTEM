import ollama
import logging
import rag_engine

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MODEL_NAME = "llama3.2:1b"

def check_model_availability():
    """Checks if the model is available locally, pulls if not."""
    try:
        # List available models
        models_response = ollama.list()
        
        # Robust parsing for different ollama versions
        model_names = []
        if 'models' in models_response:
            for m in models_response['models']:
                if isinstance(m, dict):
                    model_names.append(m.get('name', ''))
                    model_names.append(m.get('model', '')) # Some versions use 'model'

        # Check against likely variations
        if MODEL_NAME not in model_names and f"{MODEL_NAME}:latest" not in model_names:
            logging.info(f"Model {MODEL_NAME} not found. Pulling...")
            ollama.pull(MODEL_NAME)
            logging.info(f"Model {MODEL_NAME} pulled successfully.")
        else:
            logging.info(f"Model {MODEL_NAME} is ready.")
    except Exception as e:
        logging.warning(f"Error checking model list ({e}). Attempting pull to be safe...")
        try:
            ollama.pull(MODEL_NAME)
        except Exception as pull_error:
            logging.error(f"Failed to pull model: {pull_error}")

def analyze_ticket(title, description, priority, category):
    """
    Uses the LLM to generate a resolution.
    Returns a tuple (category/placeholder, resolution).
    """
    
    # RAG Retrieval
    logging.info("Retrieving relevant context...")
    context = rag_engine.get_relevant_context(f"{title} {description}")
    
    prompt = f"""
    Context:
    {context}
    
    Ticket: {title} ({description})
    
    Instruction:
    You are an automated support engine.
    Provide a resolution for the above ticket.
    - Be concise.
    - Use bullet points.
    - Do NOT mention "As an AI" or "As a support agent".
    - Just give the comparison or solution.
    
    Resolution:
    """

    try:
        response = ollama.chat(model=MODEL_NAME, messages=[
            {'role': 'user', 'content': prompt},
        ])
        
        content = response['message']['content']
        return category, content.strip() # Return original category as we now trust user input

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        logging.error(f"LLM Error: {error_msg}")
        return "Error", f"Failed to generate resolution. Details: {error_msg}"

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        logging.error(f"LLM Error: {error_msg}")
        return "Error", f"Failed to generate resolution. Details: {error_msg}"

if __name__ == "__main__":
    # Test run
    # Ensure rag_engine is ready or mock it if needed for direct execution
    cat, res = analyze_ticket("Internet down", "My wifi is not connecting","low","software")
    print(f"Category: {cat}")
    print(f"Resolution: {res}")