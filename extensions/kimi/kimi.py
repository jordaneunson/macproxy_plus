from flask import request, render_template_string, Response
import httpx
import json

DOMAIN = "kimi.com"

API_KEY = None
API_URL = "https://api.kimi.com/coding/v1/messages"

messages = []

system_prompt = (
	"Please provide your response in plain text using only ASCII characters. "
	"Never use any special or esoteric characters that might not be supported by older systems. "
	"Your responses will be presented to the user within the body of an html document. "
	"Be aware that any html tags you respond with will be interpreted and rendered as html. "
	"Therefore, when discussing an html tag, do not wrap it in <>, as it will be rendered as html. "
	"Instead, wrap the name of the tag in <b> tags to emphasize it. "
	"You do not need to provide a <body> tag. "
	"When responding with a list, ALWAYS format it using <ol> or <ul> with individual list items wrapped in <li> tags. "
	"When responding with a link, use the <a> tag. "
	"When responding with code, always insert <pre></pre> tags with <code></code> tags nested inside. "
	"NEVER use three backticks (markdown style) when discussing code. "
	"NEVER use **this format** (markdown style) to bold text - instead, wrap text in <b> tags or <i> tags."
)

HTML_LANDING = """
<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="UTF-8">
	<title>Kimi</title>
</head>
<body>
	<center>
		<h4><font size="7"><b>KIMI</b></font></h4>
	</center>
	<center>
	<form method="post" action="/">
		<textarea name="command" rows="5" cols="50" required></textarea><br>
		<input type="submit" value="Submit">
	</form>
	</center>
</body>
</html>
"""

HTML_CONVERSATION = """
<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="UTF-8">
	<title>Kimi</title>
</head>
<body>
	<table border="0" width="100%">
		<tr>
			<td align="left" valign="middle">
				<form method="post" action="/">
					<input type="text" size="40" name="command" required autocomplete="off">
					<input type="submit" value="Submit">
				</form>
			</td>
			<td align="right" valign="middle">
				<h4><font size="4"><b>KIMI</b></font></h4>
			</td>
		</tr>
	</table>
	<hr>
	<div id="chat">
		<p>{{ output|safe }}</p>
	</div>
</body>
</html>
"""

def _init_key():
	global API_KEY
	if API_KEY is None:
		import config
		API_KEY = config.KIMI_API_KEY

def _call_kimi(msgs):
	_init_key()
	response = httpx.post(
		API_URL,
		headers={
			'x-api-key': API_KEY,
			'anthropic-version': '2023-06-01',
			'content-type': 'application/json',
			'User-Agent': 'claude-code/0.1.0'
		},
		json={
			'model': 'k2p5',
			'max_tokens': 4096,
			'system': system_prompt,
			'messages': msgs
		},
		timeout=60
	)
	data = response.json()
	if 'content' in data and len(data['content']) > 0:
		return data['content'][0].get('text', '')
	return 'Error: No response from Kimi'

def handle_request(req):
	if req.method == 'POST':
		content, status_code = handle_post(req)
	elif req.method == 'GET':
		content, status_code = handle_get(req)
	else:
		content, status_code = "Not Found", 404
	return Response(content, status=status_code, content_type='text/html')

def handle_get(request):
	return chat_interface(request), 200

def handle_post(request):
	return chat_interface(request), 200

def chat_interface(request):
	global messages
	output = ""

	if request.method == 'POST':
		user_input = request.form['command']
		messages.append({"role": "user", "content": user_input})

		response_body = _call_kimi(messages[-10:])
		messages.append({"role": "assistant", "content": response_body})

	for msg in reversed(messages[-10:]):
		if msg['role'] == 'user':
			output += f"<b>User:</b> {msg['content']}<br>"
		elif msg['role'] == 'assistant':
			output += f"<b>Kimi:</b> {msg['content']}<br>"

	if messages:
		return render_template_string(HTML_CONVERSATION, output=output)
	else:
		return render_template_string(HTML_LANDING)
