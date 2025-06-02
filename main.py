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
    except Exception as e:
        st.error(f"Error fetching branch: {e}")
        return None

def get_repo_files(owner: str, repo: str, branch: str, github_token: str = None):
    api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    headers = {"Authorization": f"token {github_token}"} if github_token else {}
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        tree = response.json().get("tree", [])
        return [item for item in tree if item["type"] == "blob"]
    except Exception as e:
        st.error(f"Error fetching files: {e}")
        return None

def fetch_github_code(raw_url: str):
    try:
        response = requests.get(raw_url)
        response.raise_for_status()
        return response.text
    except Exception as e:
        st.error(f"Error fetching file: {e}")
        return None

def get_file_extension(filename_or_url: str):
    try:
        return os.path.splitext(filename_or_url.split('?')[0])[-1].lstrip('.')
    except:
        return "plaintext"

# --- Session State Initialization ---
for key in ["repo_owner", "repo_name", "repo_files", "selected_file_path", "default_branch", "code_content", "current_file_url_display", "repo_code_full", "messages"]:
    if key not in st.session_state:
        st.session_state[key] = None if key != "repo_files" and key != "messages" else ([] if key == "repo_files" else [])

# --- Sidebar Configuration ---
with st.sidebar:
    st.header("🛠️ Configuration")
    # API Key
    gemini_api_key = os.getenv("GEMINI_API_KEY")

    # GitHub Info
    github_pat = st.text_input("GitHub PAT (optional):", type="password")
    repo_url_input = st.text_input("GitHub Repo URL", placeholder="https://github.com/user/repo")

    if st.button("Load Repository Contents"):
        owner, repo = parse_github_url(repo_url_input)
        if owner and repo:
            st.session_state.repo_owner = owner
            st.session_state.repo_name = repo
            branch = get_repo_default_branch(owner, repo, github_pat)
            if branch:
                st.session_state.default_branch = branch
                files = get_repo_files(owner, repo, branch, github_pat)
                if files:
                    st.session_state.repo_files = files
                    st.session_state.selected_file_path = None
                    st.session_state.code_content = None
                    st.session_state.repo_code_full = None
                    st.session_state.messages = []
                    st.success(f"{len(files)} files found in branch '{branch}'")
                else:
                    st.error("Could not retrieve files.")
        else:
            st.error("Invalid GitHub URL.")

    if st.session_state.repo_files:
        # Load all files
        if st.button("Load Full Repository Code"):
            full_code = ""
            with st.spinner("Fetching all files..."):
                for f in st.session_state.repo_files:
                    file_path = f["path"]
                    raw_url = f"https://raw.githubusercontent.com/{st.session_state.repo_owner}/{st.session_state.repo_name}/{st.session_state.default_branch}/{file_path.replace(' ', '%20')}"
                    code = fetch_github_code(raw_url)
                    if code:
                        ext = get_file_extension(file_path)
                        full_code += f"\n\n--- FILE: {file_path} ({ext}) ---\n```{ext}\n{code}\n```"
            st.session_state.repo_code_full = full_code
            st.session_state.messages = []
            st.success("✅ Full repository loaded.")

        file_paths = [f["path"] for f in st.session_state.repo_files]
        selected_file = st.selectbox("Select single file to analyze:", ["-- None --"] + file_paths)
        if selected_file != "-- None --":
            st.session_state.selected_file_path = selected_file
            st.session_state.repo_code_full = None
            raw_url = f"https://raw.githubusercontent.com/{st.session_state.repo_owner}/{st.session_state.repo_name}/{st.session_state.default_branch}/{selected_file.replace(' ', '%20')}"
            st.session_state.current_file_url_display = f"https://github.com/{st.session_state.repo_owner}/{st.session_state.repo_name}/blob/{st.session_state.default_branch}/{selected_file}"
            code = fetch_github_code(raw_url)
            if code:
                st.session_state.code_content = code
                st.session_state.messages = []
                st.success(f"Loaded {selected_file}")
            else:
                st.error("Failed to load file.")

    if st.button("Clear All"):
        for key in ["repo_owner", "repo_name", "repo_files", "selected_file_path", "default_branch", "code_content", "current_file_url_display", "repo_code_full", "messages"]:
            st.session_state[key] = None if key != "repo_files" and key != "messages" else ([] if key == "repo_files" else [])
        st.rerun()

# --- Chat Section ---
st.title("🤖 GitHub Codebase Chatbot")

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if not gemini_api_key:
    st.warning("Please enter Gemini API Key.")
elif not st.session_state.repo_files:
    st.info("👋 Enter a GitHub URL in the sidebar and load repository contents.")
elif not st.session_state.code_content and not st.session_state.repo_code_full:
    st.info("📂 Load a single file or click 'Load Full Repository Code' to begin.")
else:
    # Display code preview
    if st.session_state.repo_code_full:
        st.info("💬 Analyzing entire repository...")
    else:
        with st.expander("📄 View Code"):
            ext = get_file_extension(st.session_state.selected_file_path)
            st.code(st.session_state.code_content, language=ext)

    # Chat input
    prompt = st.chat_input("Ask your question about the codebase...")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            placeholder = st.empty()
            response_text = ""
            try:
                genai.configure(api_key=gemini_api_key)
                model = genai.GenerativeModel(
                    model_name="gemini-2.0-flash",
                    system_instruction=f"""
You are an expert AI programming assistant.

{f"Here is the full codebase from https://github.com/{st.session_state.repo_owner}/{st.session_state.repo_name}:" if st.session_state.repo_code_full else f"Here is the file: {st.session_state.current_file_url_display}"}

{st.session_state.repo_code_full if st.session_state.repo_code_full else f"```{get_file_extension(st.session_state.selected_file_path)}\n{st.session_state.code_content}\n```"}

Answer only based on the above code. Be concise, helpful, and provide code samples in markdown if needed.
""")
                stream = model.generate_content(prompt, stream=True)
                for chunk in stream:
                    if chunk.parts:
                        response_text += chunk.text
                        placeholder.markdown(response_text + "▌")
                placeholder.markdown(response_text)
            except Exception as e:
                st.error(f"Error: {e}")
                response_text = f"Error occurred: {e}"
                placeholder.markdown(response_text)
            st.session_state.messages.append({"role": "assistant", "content": response_text})

# Optional styling
st.markdown("""
<style>
    .stChatMessage {
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)
