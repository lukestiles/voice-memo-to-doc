import os
import datetime
import logging
import textwrap
import argparse
from dataclasses import dataclass
from typing import List, Dict, Any
from pathlib import Path

from openai import OpenAI
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from config import load_config

# Constants
SCOPES = ['https://www.googleapis.com/auth/documents', 'https://www.googleapis.com/auth/drive']
GPT_CHUNK_SIZE = 2000
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

@dataclass
class ProcessingResult:
    file: str
    transcription_text: str
    doc_id: str
    doc_url: str

class TranscriptionService:
    def __init__(self, client: OpenAI):
        self.client = client
        
    def transcribe(self, audio_file_path: str) -> str:
        """Transcribe audio file using OpenAI's Whisper model."""
        logging.info(f'Transcribing {audio_file_path}')
        with open(audio_file_path, "rb") as audio_file:
            transcription = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        logging.info(f'Transcribed {audio_file_path}')
        return transcription.text

    def clean_text(self, text: str) -> str:
        """Clean and format transcribed text using GPT-4."""
        logging.debug(f'Cleaning text')
        chunks = textwrap.wrap(text, GPT_CHUNK_SIZE)
        cleaned_chunks = []

        for chunk in chunks:
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant who cleans up and formats transcriptions."},
                        {"role": "user", "content": f"Please clean up the following transcription by fixing any misspellings, adding line breaks, paragraph breaks, and appropriate punctuation:\n\n{chunk}"}
                    ]
                )
                cleaned_chunks.append(response.choices[0].message.content)
            except Exception as e:
                logging.error(f'Failed to clean text chunk: {e}')
                raise

        return '\n'.join(cleaned_chunks)

class GoogleDocsService:
    def __init__(self, config: Dict[str, str]):
        self.config = config
        self.creds = self._get_credentials()
        self.docs_service = build('docs', 'v1', credentials=self.creds)
        self.drive_service = build('drive', 'v3', credentials=self.creds)

    def _get_credentials(self) -> Credentials:
        """Get or refresh Google API credentials."""
        creds = None
        token_path = Path(self.config['TOKEN_JSON'])
        
        logging.debug(f'Getting credentials from {token_path}')
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        
        if not creds or not creds.valid:
            logging.debug(f'Token file does not exist: {token_path}')
            if creds and creds.expired and creds.refresh_token:
                logging.debug(f'Cleaning text')
                creds.refresh(Request())
            else:
                logging.debug(f'Cleaning text')
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.config['CREDENTIALS_JSON'], SCOPES)
                creds = flow.run_local_server(port=0)
                
            logging.debug(f'Writing token to {token_path}')
            token_path.write_text(creds.to_json())
            
        return creds

    def create_document(self, title: str) -> Dict[str, str]:
        """Create a new Google Doc and return its ID and URL."""
        doc = self.docs_service.documents().create(body={'title': title}).execute()
        doc_id = doc.get('documentId')
        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        return {'id': doc_id, 'url': doc_url}

    def append_text(self, doc_id: str, text: str) -> None:
        """Append text to an existing Google Doc."""
        document = self.docs_service.documents().get(documentId=doc_id).execute()
        end_index = document['body']['content'][-1]['endIndex']

        requests = [{
            'insertText': {
                'location': {'index': end_index - 1},
                'text': text
            }
        }]

        self.docs_service.documents().batchUpdate(
            documentId=doc_id, 
            body={'requests': requests}
        ).execute()
        logging.info(f'Appended text to Google Doc {doc_id}')

class AudioProcessor:
    def __init__(self, config: Dict[str, str]):
        self.openai_client = OpenAI(
            organization=config['OPENAI_ORGANIZATION'],
            project=config['OPENAI_PROJECT'],
            api_key=config['OPENAI_API_KEY']
        )
        self.transcription_service = TranscriptionService(self.openai_client)
        self.docs_service = GoogleDocsService(config)

    def process_files(
        self, 
        files: List[str], 
        directory: str, 
        output_title: str = None
    ) -> List[ProcessingResult]:
        """Process multiple audio files and create a Google Doc with transcriptions."""
        if not output_title:
            output_title = datetime.datetime.now().strftime(DEFAULT_DATE_FORMAT)

        # Create Google Doc
        doc_info = self.docs_service.create_document(output_title)
        results = []

        for file in files:
            file_path = os.path.join(directory, file)
            file_stats = os.stat(file_path)
            file_metadata = (f"{file} {datetime.datetime.fromtimestamp(file_stats.st_mtime).strftime(DEFAULT_DATE_FORMAT)}")

            # Process file
            transcription = self.transcription_service.transcribe(file_path)
            clean_transcription = self.transcription_service.clean_text(transcription)
            
            # Format and append to document
            formatted_text = (f"{file_metadata}\n\n{clean_transcription}\n"
                            f"{'---'}\n\n")
            self.docs_service.append_text(doc_info['id'], formatted_text)

            results.append(ProcessingResult(
                file=file,
                transcription_text=clean_transcription,
                doc_id=doc_info['id'],
                doc_url=doc_info['url']
            ))

        return results

def setup_logging(verbose: bool) -> None:
    """Configure logging based on verbosity level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Process audio files for transcription and cleaning'
    )
    parser.add_argument('-f', '--files', nargs='+', required=True,
                      help='List of audio files to process')
    parser.add_argument('-d', '--directory', required=True,
                      help='Directory containing the audio files')
    parser.add_argument('-o', '--output',
                      help='Output document name (default: current timestamp)')
    parser.add_argument('-v', '--verbose', action='store_true',
                      help='Enable verbose logging')
    parser.add_argument('-e', '--env',
                      choices=['development', 'testing', 'production'],
                      default='development',
                      help='Environment to use (default: development)')
    
    return parser.parse_args()

def main() -> int:
    args = parse_arguments()
    setup_logging(args.verbose)

    logging.debug(f'args: {args}')
    # Validate directory
    if not os.path.isdir(args.directory):
        logging.error(f"Directory does not exist: {args.directory}")
        return 1

    # Validate files
    files_to_process = []
    for file in args.files:
        file_path = os.path.join(args.directory, file)
        if not os.path.isfile(file_path):
            logging.warning(f"File does not exist: {file_path}")
            continue
        files_to_process.append(file)

    if not files_to_process:
        logging.error("No valid files to process")
        return 1

    try:
        config = load_config(args.env)
        processor = AudioProcessor(config)
        results = processor.process_files(
            files=files_to_process,
            directory=args.directory,
            output_title=args.output
        )
        
        logging.info(f"Successfully processed {len(results)} files")
        for result in results:
            logging.info(f"Processed file: {result.file}")
            logging.info(f"Document URL: {result.doc_url}")
        
        return 0
        
    except Exception as e:
        logging.error(f"Error processing files: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main())