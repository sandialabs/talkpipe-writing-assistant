import threading

from talkpipe.llm.chat import LLMPrompt
from talkpipe.pipe.basic import fillTemplate
from talkpipe.pipe.io import Print

from .definitions import Metadata

_paragraph_lock = threading.Lock()

def get_system_prompt(generation_mode: str) -> str:
    """Get system prompt based on generation mode"""
    base_context = """You are an expert writing assistant. Your role is to help improve written content with precision and skill.

CRITICAL: Respond ONLY with the requested output. Do not include explanations, commentary, or meta-text unless specifically asked.

"""

    if generation_mode == "ideas":
        return f"""
        {base_context}
        Analyze the current paragraph and generate 4-6 specific, actionable improvement suggestions.

        Structure your response as a bulleted list covering these areas:
        • CONTENT: Specific information to add, clarify, expand, or reorganize
        • STRUCTURE: How to better organize or sequence the ideas
        • STYLE: Concrete changes to tone, voice, word choice, or sentence variety
        • CLARITY: Ways to make complex ideas more accessible and understandable
        • FLOW: Specific transition improvements and logical connections
        • IMPACT: Methods to make the writing more engaging or persuasive

        Each bullet must be:
        - Specific to the actual content provided
        - Actionable (the writer can immediately implement it)
        - Focused on one clear improvement

        Example format:
        • Add a concrete example after "X concept" to illustrate the point for readers
        • Replace passive voice in sentence 2 with active voice for stronger impact
        • Connect the second and third ideas with a transitional phrase showing causation
        """
    elif generation_mode == "rewrite":
        return f"""
        {base_context}
        Completely rewrite the current paragraph to maximize clarity, engagement, and impact.

        Guidelines:
        - Preserve the core message and key facts
        - Feel free to restructure, reorder, or rephrase everything
        - Add relevant details or examples if they strengthen the point
        - Remove redundant or weak content
        - Use stronger, more precise language
        - Ensure smooth logical flow
        - Match the specified tone and style requirements
        - If no draft is provided, create compelling new content that fits the context

        Output only the rewritten paragraph.
        """
    elif generation_mode == "improve":
        return f"""
        {base_context}
        Enhance the provided current while preserving its essential structure and meaning.

        Focus on:
        - Strengthening word choices (replace weak or vague terms)
        - Improving sentence flow and rhythm
        - Adding precision and clarity
        - Enhancing transitions between ideas
        - Correcting any awkward phrasing
        - Ensuring consistency in tone and style
        - Making the writing more engaging without changing the core message

        Keep the original organization and main ideas intact. Make targeted improvements that elevate the quality without fundamental restructuring.

        Output only the improved paragraph.
        """
    elif generation_mode == "proofread":
        return f"""
        {base_context}
        Proofread the current paragraph for errors and clarity issues.

        Correct ONLY:
        - Grammar errors
        - Spelling mistakes
        - Punctuation errors
        - Basic clarity issues (unclear pronoun references, etc.)
        - Obvious typos

        Do NOT:
        - Change the meaning or structure
        - Add new content or ideas
        - Rewrite for style
        - Make subjective improvements

        Make the minimum changes necessary for correctness. Preserve the author's voice and intent.

        Output only the corrected paragraph.
        """
    else:
        # Default to rewrite
        return f"""
        {base_context}
        Rewrite or improve the provided paragraph to enhance its effectiveness.

        If a draft is provided: Rewrite it for maximum clarity and impact while preserving key information.
        If no draft is provided: Create compelling new content that fits the context and requirements.

        Focus on clarity, engagement, and strong communication.

        Output only the final paragraph.
        """


PROMPT_TEMPLATE = """
DOCUMENT CONTEXT:
Title: {title}
Target Audience: {metadata.target_audience}
Writing Style: {metadata.writing_style}
Tone: {metadata.tone}
Background Context: {metadata.background_context}
Special Instructions: {metadata.generation_directive}
Word Limit: {metadata.word_limit} words (approximate)

SURROUNDING CONTEXT:

================================

Previous paragraph: 

{prev_paragraph}

================================

Current paragraph to assist with:

{text}

================================

Next paragraph: 

{next_paragraph}

=================================

TASK: {generation_mode} the current paragraph using the context and requirements above.
"""

def new_paragraph(text: str, metadata: Metadata, title: str = "", prev_paragraph: str = "", next_paragraph: str = "", generation_mode: str = "rewrite") -> str:

    with _paragraph_lock:
        # Get the appropriate system prompt based on generation mode
        system_prompt = get_system_prompt(generation_mode)
        print(f"=== Generation mode: {generation_mode} ===")
        print(f"=== System prompt: {system_prompt} ===")

        f = (fillTemplate(template=PROMPT_TEMPLATE)
            | Print()
            | LLMPrompt(system_prompt=system_prompt, multi_turn=False, source=metadata.source, model=metadata.model))
        f = f.as_function(single_in=True, single_out=True)


        result = f({"text": text, "metadata": metadata, "title": title, "prev_paragraph": prev_paragraph, "next_paragraph": next_paragraph, "generation_mode": generation_mode})

        # Clean up the result to prevent extra newlines
        if isinstance(result, str):
            cleaned_result = result.strip()
            print(f"=== Generated text cleaned: {len(result)} -> {len(cleaned_result)} chars ===")
            return cleaned_result

        return result


