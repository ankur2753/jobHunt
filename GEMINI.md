# Security rule: API keys and secrets

Never print, output, or include raw API keys, secrets, or passwords in tool call arguments or in chat responses. 

If you need to update a file that contains secrets, handle it carefully. Do not use file replacement tools to pass the raw key in the tool arguments. This logs the key in the conversation transcript. 

Instead:
1. Instruct the user to manually update the secret values.
2. If you must edit the file, only edit the non-secret parts. Leave placeholders like `YOUR_KEY_HERE` for the secrets.

# Common failures 

- Use a virtual environment to run this project.
