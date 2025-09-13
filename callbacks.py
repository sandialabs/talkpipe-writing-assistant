from talkpipe import compile
import threading
from talkpipe.pipe.basic import fillTemplate
from talkpipe.pipe.io import Print
from talkpipe.llm.chat import LLMPrompt
from definitions import Metadata

_paragraph_lock = threading.Lock()

SYSTEM_PROMPT = """
    Write a short paragraph based on the provided main point and current draft.  
    If the current draft is provided, focus on improving that draft.
    """


PROMPT_TEMPLATE = """
    Writing Style: {metadata.writing_style}
 
    Tone: {metadata.tone}

    Target Audience: {metadata.target_audience}

    Background Context: {metadata.background_context}

    Special Directions: {metadata.generation_directive}

    Approximate Word Limit: {metadata.word_limit}

    Main Point: {main_point}

    Current Draft: {text}
"""


def new_paragraph(main_point: str, text: str, metadata: Metadata) -> str:
    with _paragraph_lock:
        f = (fillTemplate(template=PROMPT_TEMPLATE)  
            | Print()
            | LLMPrompt(system_prompt=SYSTEM_PROMPT, multi_turn=False, source=metadata.source, model=metadata.model) 
            | Print())
        f = f.as_function(single_in=True, single_out=True)


        return f({"main_point": main_point, "text": text, "metadata": metadata})


