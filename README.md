## Install Streamlit using command line

### Create an environment using venv

1. Clone this repo
2. In terminal, type:
  ```
    python -m venv .venv
  ```
3. A folder named ".venv" will appear in your project. This directory is where your virtual environment and its dependencies are installed.

### Activate your environment

4. Use one of the following commands
  ```
    # Windows command prompt
    .venv\Scripts\activate.bat
    
    # Windows PowerShell
    .venv\Scripts\Activate.ps1
    
    # macOS and Linux
    source .venv/bin/activate
  ```

5. Once activated, you will see your environment name in parentheses before your prompt. "(.venv)"

### Install Streamlit in your environment
6. In terminal, type:
  ```
    pip install streamlit
  ```
7. You can run a Streamlit Hello example app
  ```
    streamlit hello
  ```
  or 
  ```
    python -m streamlit hello
  ```
8. To run **FlinkCouchBaseApp**
  ```
    streamlit run app.py
  ```
  or 
  ```
    python -m streamlit run app.py
  ```
