import ollama
import logging
import re

import config
import rag_engine

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MODEL_NAME = "llama3.2:1b"
GENERIC_RESPONSE_PATTERNS = (
    "contact support",
    "reach out to your administrator",
    "not enough information",
    "unable to determine",
    "please provide more details",
)
UNCERTAINTY_PATTERNS = (
    "might be",
    "could be",
    "possibly",
    "not sure",
    "cannot confirm",
)

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

def _slugify_filename(text):
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return "_".join(tokens[:6]) if tokens else "missing_knowledge_article"

def _suggest_kb_filename(title, description, category):
    source_text = f"{title} {description}".strip().lower()
    tokens = [
        token for token in re.findall(r"[a-z0-9]+", source_text)
        if token not in {"the", "and", "for", "with", "from", "that", "this", "have", "need", "cannot", "cant"}
    ]
    phrase = " ".join(tokens[:6]) or category or "knowledge gap"
    return f"{_slugify_filename(phrase)}_guide.md"

def _response_quality_adjustment(resolution_text):
    text = (resolution_text or "").strip()
    if not text:
        return -0.2

    lowered = text.lower()
    adjustment = 0.0

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    bullet_lines = [
        line for line in lines
        if line.startswith(("-", "*", "1.", "2.", "3.", "4.", "5."))
    ]
    if len(bullet_lines) >= 2:
        adjustment += 0.08

    if 80 <= len(text) <= 1200:
        adjustment += 0.08
    elif len(text) < 40:
        adjustment -= 0.1

    if re.search(r"\b(check|verify|restart|reboot|open|run|update|clear|enable|disable|reset)\b", lowered):
        adjustment += 0.06

    if any(pattern in lowered for pattern in GENERIC_RESPONSE_PATTERNS):
        adjustment -= 0.22
    if any(pattern in lowered for pattern in UNCERTAINTY_PATTERNS):
        adjustment -= 0.12

    return max(-0.35, min(0.25, adjustment))


def _calculate_confidence(retrieval_score, top_retrieval_score, kb_context_found, resolution_text, had_error):
    if had_error:
        return 0.0

    retrieval_score = max(0.0, min(1.0, float(retrieval_score or 0.0)))
    top_retrieval_score = max(0.0, min(1.0, float(top_retrieval_score or retrieval_score)))

    confidence = 0.18
    confidence += retrieval_score * 0.5
    confidence += top_retrieval_score * 0.25
    if kb_context_found:
        confidence += 0.18
    confidence += _response_quality_adjustment(resolution_text)

    if not kb_context_found and top_retrieval_score < 0.15:
        confidence = min(confidence, 0.55)

    return max(0.0, min(1.0, round(confidence, 3)))


def _determine_resolution_status(confidence_score):
    resolved_threshold = config.get_float_env(
        "AI_CONFIDENCE_THRESHOLD",
        config.get_float_env("AI_CONFIDENC_THRESHOLD", 0.65),
    )
    unresolved_threshold = config.get_float_env("AI_UNRESOLVED_THRESHOLD", 0.45)

    resolved_threshold = max(0.0, min(1.0, float(resolved_threshold)))
    unresolved_threshold = max(0.0, min(1.0, float(unresolved_threshold)))
    if unresolved_threshold >= resolved_threshold:
        unresolved_threshold = max(0.0, round(resolved_threshold - 0.01, 3))

    if confidence_score >= resolved_threshold:
        return "resolved"
    if confidence_score < unresolved_threshold:
        return "unresolved"
    return "tentative"

def analyze_ticket(title, description, priority, category):
    """
    Uses the LLM to generate a resolution and AI quality metadata.
    """
    logging.info("Retrieving relevant context...")
    retrieval = rag_engine.get_relevant_context(f"{title} {description}")
    context = retrieval.get("context_text", "")
    retrieval_score = retrieval.get("retrieval_score", 0.0)
    top_retrieval_score = retrieval.get("top_retrieval_score", retrieval_score)
    kb_context_found = retrieval.get("kb_context_found", False)

    prompt = f"""
    Context:
    {context}
    
    Ticket: {title} ({description})
    
    Instruction:
    You are an automated support engine.
    Provide a resolution for the above ticket.
    - Be concise.
    - Return valid Markdown only.
    - Use 3-5 bullet points with `- ` as the bullet prefix.
    - Include concrete steps with checks or commands where relevant.
    - Use fenced code blocks for commands when useful.
    - If context is insufficient, say what exact detail is missing in one line.
    - Do not return HTML tags.
    - Do not wrap the full response in quotes.
    - Do NOT mention "As an AI" or "As a support agent".
    - Just give the comparison or solution.
    
    Resolution:
    """

    try:
        response = ollama.chat(model=MODEL_NAME, messages=[
            {'role': 'user', 'content': prompt},
        ])
        resolution_text = response['message']['content'].strip()
        confidence_score = _calculate_confidence(
            retrieval_score=retrieval_score,
            top_retrieval_score=top_retrieval_score,
            kb_context_found=kb_context_found,
            resolution_text=resolution_text,
            had_error=False,
        )
        resolution_status = _determine_resolution_status(confidence_score)
        return {
            "category": category,
            "resolution_text": resolution_text,
            "confidence_score": confidence_score,
            "resolution_status": resolution_status,
            "retrieval_score": retrieval_score,
            "top_retrieval_score": top_retrieval_score,
            "kb_context_found": kb_context_found,
            "context_matches": retrieval.get("matches", []),
            "suggested_kb_filename": (
                None if resolution_status == "resolved"
                else _suggest_kb_filename(title, description, category)
            ),
            "error": None,
        }

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        logging.error(f"LLM Error: {error_msg}")
        return {
            "category": category,
            "resolution_text": f"Failed to generate resolution. Details: {error_msg}",
            "confidence_score": 0.0,
            "resolution_status": "unresolved",
            "retrieval_score": retrieval_score,
            "top_retrieval_score": top_retrieval_score,
            "kb_context_found": kb_context_found,
            "context_matches": retrieval.get("matches", []),
            "suggested_kb_filename": _suggest_kb_filename(title, description, category),
            "error": error_msg,
        }

if __name__ == "__main__":
    # Test run
    # Ensure rag_engine is ready or mock it if needed for direct execution
    analysis = analyze_ticket("Configuring IP Addressing", "How to Configure IP Addressing", "High", "Network")
    print(f"Category: {analysis['category']}")
    print(f"Resolution: {analysis['resolution_text']}")
