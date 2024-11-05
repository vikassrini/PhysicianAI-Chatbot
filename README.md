# RealTime Physician Chatbot
## Demo of my chatbot working.


https://github.com/user-attachments/assets/9d0f6dc8-ebfe-4135-bd94-2031fa970dc0



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
    touch keys.toml
    ```
    You can get your OpenAI API key from here - [Link to get OpenAI API key](https://openai.com/blog/openai-api)
    ```
    # add the following API key
    [api_keys]
    service_1_key = 
    ```

6. **Setup MongoDB:(optional)**
    [Download MongoDB from here](https://www.mongodb.com/try/download/community-kubernetes-operator)
    Connect to the database using the connection string.
7. **Setup Weaviate:**
    1. Install the weaviate python client using the following command:
```        
        pip install -U weaviate-client
```       
2. Run a local instance of Weavitate:
        Install docker on your machine , do this following this [Installation Guide](https://docs.docker.com/get-started/get-docker/).
        
   Run the following command to start weavite 
 ```   
     docker compose up
 ``` 
8. **Run the application using the command:**
    ```
    uvicorn chatapp:app --reload
    ```
