import streamlit as st
import google.generativeai as genai
import requests
import os
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Streamlit configuration
st.set_page_config(page_title="GitHub Codebase Chatbot", layout="wide")

# --- Helper Functions ---
def parse_github_url(url: str):
    pattern = r"https://github\.com/([^/]+)/([^/]+)"
    match = re.match(pattern, url)
    if match:
        return match.group(1), match.group(2).split('.git')[0]
    return None, None

def get_repo_default_branch(owner: str, repo: str, github_token: str = None):
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Authorization": f"token {github_token}"} if github_token else {}
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        return response.json().get("default_branch", "main")
    except requests.exceptions.RequestException as e: # More specific exception
        st.error(f"Error fetching branch: {e}")
        return None
    except Exception as e: # Generic fallback
        st.error(f"Unexpected error fetching branch: {e}")
        return None


def get_repo_files(owner: str, repo: str, branch: str, github_token: str = None):
    api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    headers = {"Authorization": f"token {github_token}"} if github_token else {}
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        tree = response.json().get("tree", [])
        return [item for item in tree if item["type"] == "blob"]
    except requests.exceptions.RequestException as e: # More specific exception
        st.error(f"Error fetching files: {e}")
        return None
    except Exception as e: # Generic fallback
        st.error(f"Unexpected error fetching files: {e}")
        return None

def fetch_github_code(raw_url: str):
    try:
        response = requests.get(raw_url)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e: # More specific exception
        st.error(f"Error fetching file content: {e}")
        return None
    except Exception as e: # Generic fallback
        st.error(f"Unexpected error fetching file content: {e}")
        return None


def get_file_extension(filename_or_url: str):
    try:
        return os.path.splitext(filename_or_url.split('?')[0])[-1].lstrip('.')
    except:
        return "plaintext"

# --- Session State Initialization ---
# Initialize keys if they don't exist
default_values = {
    "repo_owner": None,
    "repo_name": None,
    "repo_files": [],
    "selected_file_path": None,
    "default_branch": None,
    "code_content": None,
    "current_file_url_display": None,
    "repo_code_full": None,
    "messages": []
}
for key, default_value in default_values.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# --- Sidebar Configuration ---
with st.sidebar:
    st.header("🛠️ Configuration")

    # API Key
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        st.warning("⚠️ GEMINI_API_KEY not found in .env file. Please set it up.")
        # You might want to st.stop() here or disable functionality if API key is crucial upfront
    else:
        st.success("✔️ Gemini API Key loaded from .env.")


    # GitHub Info
    github_pat = st.text_input("GitHub PAT (optional for rate limits/private repos):", type="password", key="github_pat_input")
    repo_url_input = st.text_input("GitHub Repo URL:", placeholder="https://github.com/user/repo", key="repo_url_input")

    if st.button("Load Repository Contents", key="load_repo_button"):
        if not repo_url_input:
            st.warning("Please enter a GitHub repository URL.")
        else:
            owner, repo = parse_github_url(repo_url_input)
            if owner and repo:
                st.session_state.repo_owner = owner
                st.session_state.repo_name = repo
                with st.spinner(f"Fetching default branch for {owner}/{repo}..."):
                    branch = get_repo_default_branch(owner, repo, github_pat if github_pat else None)
                
                if branch:
                    st.session_state.default_branch = branch
                    with st.spinner(f"Fetching files from branch '{branch}'..."):
                        files = get_repo_files(owner, repo, branch, github_pat if github_pat else None)
                    
                    if files is not None: # Check if files is not None (means no error in fetching)
                        st.session_state.repo_files = files
                        # Reset dependent states
                        st.session_state.selected_file_path = None
                        st.session_state.code_content = None
                        st.session_state.repo_code_full = None
                        st.session_state.messages = []
                        st.success(f"{len(files)} files found in repository (branch: '{branch}')")
                    else:
                        st.error("Could not retrieve files. Check repository permissions or URL.")
                else:
                    st.error("Could not determine the default branch. Check repository URL or PAT.")
            else:
                st.error("Invalid GitHub repository URL format.")

    if st.session_state.repo_files:
        st.markdown("---")
        st.subheader("Analyze Code")
        # Load all files button
        if st.button("Load Full Repository Code (for overview)", key="load_full_repo_button"):
            if not st.session_state.repo_files:
                st.warning("No files loaded from repository yet.")
            else:
                full_code_parts = []
                progress_bar = st.progress(0)
                status_text = st.empty()
                num_files = len(st.session_state.repo_files)

                with st.spinner("Fetching all file contents... This might take a while for large repositories."):
                    for i, f_item in enumerate(st.session_state.repo_files):
                        file_path = f_item["path"]
                        status_text.text(f"Fetching: {file_path} ({i+1}/{num_files})")
                        # Construct raw URL carefully
                        raw_url = f"https://raw.githubusercontent.com/{st.session_state.repo_owner}/{st.session_state.repo_name}/{st.session_state.default_branch}/{file_path.replace(' ', '%20')}"
                        code = fetch_github_code(raw_url)
                        if code:
                            ext = get_file_extension(file_path)
                            # Append structured file content
                            full_code_parts.append(f"\n\n--- FILE: {file_path} ---\n```{ext}\n{code}\n```")
                        else:
                            full_code_parts.append(f"\n\n--- FILE: {file_path} --- (Error fetching content)")
                        progress_bar.progress((i + 1) / num_files)
                
                st.session_state.repo_code_full = "".join(full_code_parts)
                st.session_state.code_content = None # Unset single file content
                st.session_state.selected_file_path = None # Unset single file selection
                st.session_state.messages = []
                status_text.success("✅ Full repository code concatenated for analysis.")
                progress_bar.empty()


        # Single file selection
        file_paths = ["-- Select a single file --"] + [f["path"] for f in st.session_state.repo_files]
        selected_file = st.selectbox(
            "Or, select a single file to analyze:",
            options=file_paths,
            index=0, # Default to placeholder
            key="select_single_file_sb"
        )

        if selected_file != "-- Select a single file --":
            # Only proceed if the selection is different from the current or if no file is selected yet
            if st.session_state.selected_file_path != selected_file:
                st.session_state.selected_file_path = selected_file
                st.session_state.repo_code_full = None # Unset full repo content
                st.session_state.code_content = None # Clear previous single file content before loading new one
                st.session_state.messages = []

                raw_url = f"https://raw.githubusercontent.com/{st.session_state.repo_owner}/{st.session_state.repo_name}/{st.session_state.default_branch}/{selected_file.replace(' ', '%20')}"
                st.session_state.current_file_url_display = f"https://github.com/{st.session_state.repo_owner}/{st.session_state.repo_name}/blob/{st.session_state.default_branch}/{selected_file.replace(' ', '%20')}"
                
                with st.spinner(f"Fetching content for {selected_file}..."):
                    code = fetch_github_code(raw_url)
                if code:
                    st.session_state.code_content = code
                    st.success(f"Loaded: {selected_file}")
                else:
                    st.error(f"Failed to load content for {selected_file}.")
                    st.session_state.selected_file_path = None # Reset on failure
        elif st.session_state.selected_file_path and selected_file == "-- Select a single file --": # If user deselects
             st.session_state.selected_file_path = None
             st.session_state.code_content = None


    st.markdown("---")
    if st.button("Clear All Loaded Data & Chat", key="clear_all_button"):
        for key_to_clear in default_values.keys(): # Iterate through the keys we defined for session state
            st.session_state[key_to_clear] = default_values[key_to_clear]
        st.rerun()

# --- Main Chat Section ---
st.title("🤖 GitHub Codebase Chatbot")

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Determine chatbot readiness and context
chat_ready = False
if not gemini_api_key:
    st.error("⛔ Gemini API Key is not configured. Please set GEMINI_API_KEY in your .env file.")
elif not st.session_state.repo_owner: # Check if a repo has been loaded at all
    st.info("👋 Welcome! Enter a GitHub repository URL in the sidebar and click 'Load Repository Contents'.")
elif not st.session_state.code_content and not st.session_state.repo_code_full:
    st.info("📂 Repository contents loaded. Please select a single file or click 'Load Full Repository Code' in the sidebar to begin analysis.")
else:
    chat_ready = True

if chat_ready:
    # Display code preview if a single file is loaded
    if st.session_state.code_content and st.session_state.selected_file_path:
        with st.expander(f"📄 View Code: {st.session_state.selected_file_path}", expanded=False):
            ext = get_file_extension(st.session_state.selected_file_path)
            st.code(st.session_state.code_content, language=ext, line_numbers=True)
        st.info(f"💬 Analyzing: Single file - `{st.session_state.selected_file_path}`")
    elif st.session_state.repo_code_full:
        st.info(f"💬 Analyzing: Full repository - `{st.session_state.repo_owner}/{st.session_state.repo_name}` (overview)")
        # Optionally, show a snippet or metadata about the full repo load
        # with st.expander("Full Repository Context Snippet (first 1000 chars)", expanded=False):
        # st.text(st.session_state.repo_code_full[:1000] + "...")

    # Chat input
    prompt = st.chat_input("Ask your question about the loaded codebase...")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response_text = ""
            try:
                genai.configure(api_key=gemini_api_key)

                # Determine the context and code to provide for the system instruction
                if st.session_state.repo_code_full:
                    context_header = f"You are analyzing the full codebase from the GitHub repository: https://github.com/{st.session_state.repo_owner}/{st.session_state.repo_name}."
                    code_to_analyze = st.session_state.repo_code_full
                elif st.session_state.code_content and st.session_state.selected_file_path:
                    context_header = f"You are analyzing the following file: {st.session_state.current_file_url_display} from the GitHub repository https://github.com/{st.session_state.repo_owner}/{st.session_state.repo_name}."
                    file_ext = get_file_extension(st.session_state.selected_file_path)
                    code_to_analyze = f"```{file_ext}\n{st.session_state.code_content}\n```"
                else: # Should not happen if chat_ready is true, but as a fallback
                    st.error("No code context available for analysis.")
                    st.stop()

                system_instruction = f"""You are an expert AI programming assistant.
{context_header}

The user is asking questions about the following code:
{code_to_analyze}

Please answer the user's questions based *only* on the provided code context.
Be concise and helpful. If the user asks for code, provide it in markdown format.
If the question is outside the scope of the provided code, politely state that you cannot answer.
If the provided code is very long (especially for full repository analysis), acknowledge that you might not be able to process every single detail but will do your best based on the overall structure and searchable content.
"""
                # For Gemini 1.5 Flash, which has a large context window, sending the full repo might work
                # For other models, this might be too much. Consider truncation or summarization for repo_code_full if using models with smaller context windows.
                
                model = genai.GenerativeModel(
                    model_name="gemini-1.5-flash-latest", # Use a model that supports large context if sending full repo
                    system_instruction=system_instruction
                )
                
                stream = model.generate_content(prompt, stream=True)
                for chunk in stream:
                    if chunk.parts:
                        full_response_text += chunk.text
                        placeholder.markdown(full_response_text + "▌") # Typing effect
                placeholder.markdown(full_response_text) # Final response

            except Exception as e:
                st.error(f"An error occurred with the Gemini API: {e}")
                full_response_text = f"Sorry, I encountered an error during generation: {e}"
                placeholder.markdown(full_response_text)
            
            st.session_state.messages.append({"role": "assistant", "content": full_response_text})

# Optional styling
st.markdown("""
<style>
    .stChatMessage {
        border-radius: 10px;
        padding: 1em; /* Use em for responsive padding */
        margin-bottom: 1em;
    }
    /* Example: different background for user and assistant */
    /* Adjust data-testid selector based on Streamlit version if needed */
    div[data-testid="stChatMessageContent"] p {
        margin: 0; /* Remove default paragraph margins if desired */
    }
</style>
""", unsafe_allow_html=True)