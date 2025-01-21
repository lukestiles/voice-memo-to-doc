This is a hacked together prototype to enable creating a Google Doc with one or more Voice Memos from the Apple iPhone app. My process is
# Record lots of voice memos
# Share them to a location on my laptop
# Move them files to the /tmp project directory
# Run this script with the file list and path to the directory like this: 
 (.venv) /path/to/python /path/to/project/util.py -d /path/to/project/tmp  -f file1.m4a file2.m4a file3.m4a

It relies on the OpenAI API and the Google API. 

You'll need to create a .env file with the following entries:

    CREDENTIALS_JSON=path/to/google/credentials/json
    TOKEN_JSON=path/to/google/topen/json

    OPENAI_ORGANIZATION=from your Open AI account
    OPENAI_PROJECT=from your Open AI account
    OPENAI_API_KEY=from your Open AI account

Follow these steps to get credentials.json from your GCP account

# Go to the Google Cloud Console.
# Select your project.
vNavigate to "APIs & Services" -> "Credentials."
# Click "+ Create Credentials" -> "OAuth client ID."
# Choose "Desktop app" as the application type.
# Give it a name (e.g., "Voice to Doc").
# Click "Create."
# Download the credentials.json file and place it in your project /config directory.

token.json will be created and saved on first run of the script.

For OpenAI, follow the Developer quickstart here https://platform.openai.com/docs/quickstart.