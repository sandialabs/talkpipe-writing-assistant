from talkpipe import compile

f_new_paragraph = compile(
    """
    CONST PROMPT = "Write a short paragraph based on the provided main point and current draft.  If the current draft is provided, focus on improving that draft.

    | fillTemplate[template="Main Point: {main_point}, Current Draft: {text}"]
    | llmPrompt[system_prompt=PROMPT, multi_turn=False]
    """)
f_new_paragraph = f_new_paragraph.as_function(single_in=True, single_out=True)

def new_paragraph(main_point: str,text: str) -> str:
    return f_new_paragraph({"main_point": main_point, "text": text})
