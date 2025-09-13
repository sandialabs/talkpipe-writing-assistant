from talkpipe import compile
import threading

_paragraph_lock = threading.Lock()

f_new_paragraph = compile(
    """
    CONST PROMPT = "Write a short paragraph based on the provided main point and current draft.  If the current draft is provided, focus on improving that draft.";

    | fillTemplate[template="Main Point: {main_point}, Current Draft: {text}"]
    | print
    | llmPrompt[system_prompt=PROMPT, multi_turn=False]
    | print
    """)
f_new_paragraph = f_new_paragraph.as_function(single_in=True, single_out=True)

def new_paragraph(main_point: str, text: str) -> str:
    with _paragraph_lock:
        return f_new_paragraph({"main_point": main_point, "text": text})
