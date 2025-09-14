from talkpipe import compile
import threading
from talkpipe.pipe.basic import fillTemplate
from talkpipe.pipe.io import Print
from talkpipe.llm.chat import LLMPrompt
from definitions import Metadata

_paragraph_lock = threading.Lock()

SYSTEM_PROMPT = """
    Write a short paragraph based on the provided main point and current draft.  
    Take into account all of the provided additional information.  Do not repeat
    information in the previous paragraph, but build upon it and refer to it
    if relevant.
    If the current draft is provided, focus on improving that draft.  If not, write
    an entirely new paragraph.
    """


PROMPT_TEMPLATE = """
    Document Title: {title}

    Writing Style: {metadata.writing_style}

    Tone: {metadata.tone}

    Target Audience: {metadata.target_audience}

    Background Context: {metadata.background_context}

    Special Directions: {metadata.generation_directive}

    Approximate Word Limit: {metadata.word_limit}

    Previous Paragraph: {prev_paragraph}

    Next Paragraph: {next_paragraph}

    Main Point for current paragraph: {main_point}

    Current paragraph draft: {text}

"""


def new_paragraph(main_point: str, text: str, metadata: Metadata, title: str = "", prev_paragraph: str = "", next_paragraph: str = "") -> str:
    with _paragraph_lock:
        f = (fillTemplate(template=PROMPT_TEMPLATE)
            | Print()
            | LLMPrompt(system_prompt=SYSTEM_PROMPT, multi_turn=False, source=metadata.source, model=metadata.model)
            | Print())
        f = f.as_function(single_in=True, single_out=True)


        return f({"main_point": main_point, "text": text, "metadata": metadata, "title": title, "prev_paragraph": prev_paragraph, "next_paragraph": next_paragraph})


