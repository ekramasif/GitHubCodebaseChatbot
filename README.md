# GitHub Codebase Chatbot

A Streamlit app that lets you chat with any public GitHub repository's codebase using AI.

## Features

- Load any public GitHub repository by URL
- Optionally use a GitHub Personal Access Token for private repos or higher rate limits
- View and analyze the full repository or select a single file
- Ask questions about the codebase and get AI-powered answers
- Supports large context windows with Gemini 2.0 Flash

## Setup

1. **Clone this repository**  
   ```sh
   git clone https://github.com/ekramasif/GitHubCodebaseChatbot.git
   cd GitHubCodebaseChatbot
   ```

2. **Install dependencies**  
   ```sh
   pip install -r requirements.txt
   ```

3. **Set up environment variables**  
   - Create a `.env` file in the project root:
     ```
     GEMINI_API_KEY=your_gemini_api_key_here
     ```
   - (Optional) Add your GitHub Personal Access Token in the sidebar for private repos.

4. **Run the app**  
   ```sh
   streamlit run main.py
   ```

## Usage

- Enter a GitHub repository URL in the sidebar and click "Load Repository Contents".
- Optionally, enter your GitHub PAT for private repositories.
- Load the full repository code or select a single file to analyze.
- Ask questions about the codebase in the chat interface.

## Requirements

- Python 3.8+
- See `requirements.txt` for Python dependencies.

## License

MIT License

---
*This project is for educational and research purposes. Use responsibly.*
