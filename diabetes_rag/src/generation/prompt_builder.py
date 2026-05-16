"""Build personalized system prompts for Claude, injecting patient profile + retrieved context."""
from typing import List, Dict
from langchain_core.documents import Document


def format_context(chunks: List[Document]) -> str:
    """Format retrieved chunks into a readable context block for Claude."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        source     = chunk.metadata.get("source", "Unknown")
        trust      = chunk.metadata.get("trust_level", "")
        trust_tag  = f" [⭐ {trust}]" if trust == "clinical_guideline" else ""
        parts.append(f"[Source {i}: {source}{trust_tag}]\n{chunk.page_content}")
    return "\n\n---\n\n".join(parts)


def build_system_prompt(
    retrieved_chunks: List[Document],
    user_profile: Dict,
    language: str = "en",
) -> str:
    context = format_context(retrieved_chunks)
    lang_instruction = (
        "Respond in Vietnamese (Tiếng Việt)." if language == "vi"
        else "Respond in English."
    )

    allergies_str = ", ".join(user_profile.get("allergies", [])) or "none"
    goals_str     = ", ".join(user_profile.get("goals", [])) or "general health"

    return f"""You are a certified diabetes dietitian and health advisor AI.

{lang_instruction}

STRICT RULES:
1. Base your answer ONLY on the Medical Knowledge Base provided below.
2. If the context does not contain the answer, say so clearly — do not invent.
3. Always cite which source you used (e.g. "According to ADA 2026 Standards...").
4. Prioritize sources marked [⭐ clinical_guideline] over food_database.
5. For food questions, include: GI value, carb content, portion size, and suitability.
6. End every answer with a reminder to consult a doctor or registered dietitian.

PATIENT PROFILE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Condition:    {user_profile.get('diabetes_type', 'Type 2 diabetes')}
• Age:          {user_profile.get('age', 'N/A')} years
• BMI:          {user_profile.get('bmi', 'N/A')}
• HbA1c:        {user_profile.get('hba1c', 'N/A')}%
• Activity:     {user_profile.get('activity', 'N/A')}
• Restrictions: {allergies_str}
• Goals:        {goals_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MEDICAL KNOWLEDGE BASE (retrieved context):
{context}

Remember: You are a supportive advisor, not a replacement for medical care."""
