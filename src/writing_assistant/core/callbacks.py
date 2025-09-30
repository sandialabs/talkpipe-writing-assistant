import threading
from talkpipe.pipe.basic import fillTemplate
from talkpipe.pipe.io import Print
from talkpipe.llm.chat import LLMPrompt
from .definitions import Metadata

_paragraph_lock = threading.Lock()

def get_system_prompt(generation_mode: str) -> str:
    """Get system prompt based on generation mode"""
    base_context = """You are a writing assistant. Help the user improve the draft they provide.
    Do not explain or comment on your changes - just provide the rewritten paragraph.

    """

    if generation_mode == "ideas":
        return f"""
        {base_context}
        Analyze the current paragraph and provide a bulleted list of specific ideas for improving it.
        Focus on providing actionable suggestions in these areas:
        • Content: What information could be added, clarified, or reorganized
        • Style: How the writing style, tone, or voice could be enhanced
        • Approach: Alternative ways to present or structure the information
        • Flow: How transitions and connections could be improved

        Format your response as a clear bulleted list with 4-6 specific, actionable suggestions.
        Each bullet should be concise but detailed enough to be implementable.
        """
    elif generation_mode == "rewrite":
        return f"""
        {base_context}
        Write or rewrite the current paragraph based on the current draft.
        If the current draft is provided, completely rewrite it to be clearer and more engaging.
        Keep useful content and main point from the draft, but do not be constrained by
        its structure or wording. Add new ideas and ignore parts that do not fit well.
        If no draft is provided, write an entirely new paragraph.
        """
    elif generation_mode == "improve":
        return f"""
        {base_context}
        Improve and enhance the current paragraph draft.
        Focus on making the existing draft better by improving clarity, flow, word choice,
        and overall quality. Keep the original structure and meaning but make it more polished.
        If no draft is provided, write a high-quality new paragraph.
        """
    elif generation_mode == "proofread":
        return f"""
        {base_context}
        Proofread and correct the current paragraph draft for grammar and spelling.
        Leave the current meaning and structure intact.  Do not add new content.
        Do not rewrite or improve the draft content - only fix errors.
        Make minimal changes - only what's necessary for correctness and clarity.
        """
    else:
        # Default to rewrite
        return f"""
        {base_context}
        Write or improve the current paragraph draft based on the current draft.
        If the current draft is provided, focus on improving that draft but rewrite it
        if there are conflicts. If not, write an entirely new paragraph.
        """


PROMPT_TEMPLATE = """
    Document Title: {title}

    Writing Style: {metadata.writing_style}

    Tone: {metadata.tone}

    Target Audience: {metadata.target_audience}

    Background Context: {metadata.background_context}

    Special Directions: {metadata.generation_directive}

    Approximate Word Limit: {metadata.word_limit}

    Paragraph before the current paragraph: {prev_paragraph}

    ==============

    Current paragraph draft: {text}

    ===============

    Paragraph after the current paragraph: {next_paragraph}

    Based on the above information, {generation_mode} the current paragraph draft.
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


