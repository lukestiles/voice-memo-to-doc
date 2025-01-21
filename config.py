import configparser
import os

def load_config(env='development'):

    # Load environment variables with defaults
    config_values = {
        'OPENAI_ORGANIZATION': os.environ.get('OPENAI_ORGANIZATION', ''),
        'OPENAI_PROJECT': os.environ.get('OPENAI_PROJECT', ''),
        'OPENAI_API_KEY': os.environ.get('OPENAI_API_KEY', ''),
        'CREDENTIALS_JSON': os.environ.get('CREDENTIALS_JSON', os.path.join(os.sep, 'config', 'credentials.json')),
        'TOKEN_JSON': os.environ.get('TOKEN_JSON', os.path.join(os.sep, 'config', 'token.json'))
    }

    return config_values
