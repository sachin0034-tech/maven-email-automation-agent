# Email Extractor from CSV

A Streamlit application that extracts email addresses from CSV files using OpenAI API.

## Features

- Upload CSV files
- Secure API key input via sidebar
- AI-powered email extraction using OpenAI
- Display extracted emails in a table
- Download results as CSV
- Statistics (total emails, unique domains, etc.)

## Installation

1. Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

1. Run the Streamlit application:
```bash
streamlit run main.py
```

2. Enter your OpenAI API key in the sidebar
3. Upload a CSV file
4. Click "Extract Emails" to process the file
5. Download the extracted emails as a CSV file

## Requirements

- Python 3.7+
- OpenAI API key
- Streamlit
- Pandas
- OpenAI Python library

## Notes

- The application uses both OpenAI API and regex pattern matching to ensure comprehensive email extraction
- Your API key is only used for processing and is not stored
- The application processes CSV files of any size (with token limits for OpenAI API)



