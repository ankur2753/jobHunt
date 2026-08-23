# Security Rule: API Keys & Secrets

**NEVER** print, output, or include raw API keys, secrets, or passwords in tool call arguments (such as `replace_file_content`, `run_command`, etc.) or in chat responses. 

If you need to update a file that contains secrets (like a `.env` file), you must handle it carefully. Do not use `replace_file_content` or `write_to_file` to pass the raw key in the tool arguments, as this logs the key in the conversation transcript. 

Instead:
1. Instruct the user to manually update the secret values.
2. Or, if you must edit the file, only edit the non-secret parts of the file, leaving placeholders like `YOUR_KEY_HERE` for the secrets.


# common Filures 

- use Venv to run this project
