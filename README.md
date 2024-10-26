# RealTime Physician Chatbot

## Steps to run the bot
1. **Clone the Repository:**
    ```
    git clone https://github.com/vikassrini/Chatbot.git
    cd Chatbot 
    ```

2. **Set Up a Virtual Environment (Optional but Recommended):**
    ```
    # For macOS and Linux:
    python3 -m venv venv

    # For Windows:
    python -m venv venv
    ```

3. **Activate the Virtual Environment:**
    ```
    # For macOS and Linux:
    source venv/bin/activate

    # For Windows:
    .\venv\Scripts\activate
    ```

4. **Install Required Dependencies:**
```pip install -r reuqirements.txt```


5. **Set up the Environment Variables:**

    Create .toml file
    ```
    touch .secrets/<file-name>.toml
    ```
    You can get your OpenAI API key from here - [Link to get OpenAI API key](https://openai.com/blog/openai-api)
    ```
    # add the following API key
    [api_keys]
    service_1_key = 
    ```

6. **Setup MongoDB:**
    [Download MongoDB from here](https://www.mongodb.com/try/download/community-kubernetes-operator)
    Connect to the database using the connection string.

7. **Run the application using the command:**
    ```
    uvicorn chatapp:app --reload
    ```
