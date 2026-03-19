from flask import request, render_template_string
from openai import OpenAI
import config

client = OpenAI(api_key=config.OPEN_AI_API_KEY)

DOMAIN = "seven.com"

messages = []

SYSTEM_PROMPTS = [
    {"role": "system", "content": (
        "You are Seven, Jordan's personal AI assistant. "
        "You're sharp, direct, no fluff. You have opinions and you're genuinely helpful. "
        "Keep responses concise -- this is being rendered on a 1986 Macintosh Plus with a 512x342 screen."
    )},
    {"role": "system", "content": (
        "Your responses will be presented within the body of an HTML document. "
        "Any HTML tags you use will be rendered. Use only HTML 3.2 compatible tags: "
        "b, i, br, pre, ul, ol, li, a. Never use markdown formatting like **bold** or ```code```. "
        "Keep line lengths short. No CSS, no JavaScript."
    )},
]

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head><title>Seven</title></head>
<body>
<h4><b>Seven</b></h4>
<hr>
<form method="post" action="/">
<input type="text" size="50" name="command" required autocomplete="off">
<input type="submit" value="Send">
<input type="submit" name="clear" value="Clear">
</form>
<hr>
<div>
{{ output|safe }}
</div>
</body>
</html>"""

def handle_request(req):
    global messages
    if req.method == 'POST':
        if 'clear' in req.form:
            messages = []
            return render_template_string(HTML_TEMPLATE, output="<i>Conversation cleared.</i>"), 200

        user_input = req.form.get('command', '').strip()
        if user_input:
            messages.append({"role": "user", "content": user_input})
            msgs_to_send = SYSTEM_PROMPTS + messages[-10:]
            try:
                response = client.chat.completions.create(
                    model="gpt-4.1",
                    messages=msgs_to_send
                )
                reply = response.choices[0].message.content
                messages.append({"role": "assistant", "content": reply})
            except Exception as e:
                messages.append({"role": "assistant", "content": f"Error: {str(e)}"})

    output = ""
    for msg in reversed(messages[-10:]):
        if msg['role'] == 'user':
            output += f"<b>Jordan:</b> {msg['content']}<br>"
        elif msg['role'] == 'assistant':
            output += f"<b>Seven:</b> {msg['content']}<br>"
        output += "<br>"

    return render_template_string(HTML_TEMPLATE, output=output), 200
