from openai import AsyncOpenAI, OpenAIError
import tiktoken
import regex as re 
import pdfplumber
import weaviate

# Initialize the client
client = weaviate.Client("http://localhost:8080")
class OpenAIService:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.chatbot_prompt = {
            "role": "system",
            "content": (
                "You are a professional physician. Answer health-related queries in a concise, informative manner. "
                "You do not need to provide disclaimers. Ask follow-up questions when necessary. You are supposed to "
                "answer all queries about general illnesses and provide suggestions on what medicines to take and what "
                "interventions are needed for those illnesses. For example, if a user says they have fever, body ache, "
                "and headache, respond with relevant responses like 'How long have you had these symptoms?' or 'What is "
                "your oxygen saturation?' You seem to be having a viral infection."
            )
        }
        self.context_summarizer_prompt = {
            "role": "system",
            "content": (
                "The messages passed along with this prompt provide context for a chatbot conversation. "
                "They are currently exceeding the token limit. Summarize all information from the 'user' "
                "and 'assistant' content into one concise summary in the following format:\n\n"
                "question: summary of all user prompts followed by a question mark (?).\n"
                "answer: summary of all assistant responses followed by 3 periods (..)."
            )
        }
    async def store_chunks_in_weaviate(self, chunks):
        
        try:
            # Ensure the 'client' is initialized and available
            class_name = "TextChunk"
            global client
            # Check if class already exists, if not, create it
            if not client.schema.contains({"class": class_name}):
                schema = {
                    "class": class_name,
                    "vectorizer": "text2vec-openai",  # Built-in vectorizer
                    "properties": [
                        {
                            "name": "content",
                            "dataType": ["text"],
                        },
                    ],
                }
                client.schema.create_class(schema)
                print("Class created successfully in Weaviate.")
            else:
                print("Class already exists.")
        except Exception as e:
            print(f"An error occurred while processing Weaviate schema: {e}")
            
            # Store each chunk in Weaviate
            for chunk in chunks:
                data_object = {
                    "content": chunk,
                }

                # Add the data object to Weaviate
                client.data_object.create(
                    data_object=data_object,
                    class_name=class_name,
                )
                print(f"Stored chunk in Weaviate: {chunk[:60]}...") 

    def count_tokens(self, messages):
        """
        Counts the number of tokens in a list of messages.
        
        Parameter:
        ----------
        messages : List of dictionaries
            Used to store the context of the previous messages and 
            pass the same to the LLM.

        Returns:
        -------
        int
            Returns the number of tokens in the "content" messages.
        """
        encoding = tiktoken.encoding_for_model("gpt-4")    # Adjust model if needed
        total_tokens = 0
        for message in messages:
            total_tokens += len(encoding.encode(message['content']))
        return total_tokens
    
    async def query_weaviate(self, query_text):
    
        response = client.query.get("TextChunk", ["content"]) \
                .with_near_text({"concepts": [query_text]}) \
                .with_limit(5).do()
        matches = [result["content"] for result in response["data"]["Get"]["TextChunk"]]
        print("Top matches from Weaviate:", matches)
        return matches


    async def get_gpt_response(self, sessiondata, userprompt,filepath=None):
        """
        Returns the response string for the user request after
        constructing a prompt based on the previous context, system
        prompt and current user prompt.

        Parameters:
        -----------
        sessiondata: dict
            Contains session data until this point.

        userprompt: str 
            Current user prompt

        Returns:
        --------
        str:
            Returns a response to the current user prompt.
        """
        try:
            message = []
        
            for question, answer in sessiondata["QandA"].items():  
                dic = {"role": "user", "content": f"{question}"}
                message.append(dic)
                dic = {"role": "assistant", "content": f"{answer}"}
                message.append(dic)

            if filepath:
                with pdfplumber.open(filepath) as pdf:
                    pages=pdf.pages
                    chunks=[] 
                    for page in pages:
                        text=page.extract_text()
                        chunks.append(text)
                    pdf.close()
                await self.store_chunks_in_weaviate(chunks)
                
                relevant_chunks = await self.query_weaviate(userprompt)
                userprompt = {"role": "user", "content": f"{userprompt} + consider this context while responding: {relevant_chunks}"}
            else: 
                userprompt = {"role": "user", "content": f"{userprompt}"}

            if self.count_tokens(message) > 2096:
                print("Token limit exceeded. Summarizing context...")  
                summarized_question, summarized_answer = await self.summarize_context(message)
                message = [summarized_question, summarized_answer]  

            messages = [self.chatbot_prompt]
            messages.extend(message)
            messages.append(userprompt)

            response = await self.client.chat.completions.create(
                model="gpt-4",  
                messages=messages  
            )
            return response.choices[0].message.content
        except OpenAIError as e:
            raise Exception(f"OpenAI Error: {e}")

    async def summarize_context(self, messages):
        """
        Summarises the previous context and returns the summarized context
        as a list of dictionaries. 
        
        Parameters:
        -----------
        messages: list of dictionaries
            Contains the previous context.
        
        Returns:
        --------
        returns the summarized context as a list of dictionaries. 
        """
        try:
            summary_response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[self.context_summarizer_prompt] + messages,  
                max_tokens=500  
            )

            summarized_content = summary_response.choices[0].message.content
            question_match = re.search(r"question:\s*(.*?)\s*answer:", summarized_content, re.DOTALL)
            answer_match = re.search(r"answer:\s*(.*?)\s*\.\.\.", summarized_content, re.DOTALL)

            if question_match and answer_match:
                summarized_question = question_match.group(1).strip()
                summarized_answer = answer_match.group(1).strip()

                question_summary = {"role": "user", "content": summarized_question + "?"}
                response_summary = {"role": "assistant", "content": summarized_answer + "..."}

                return question_summary, response_summary
            else:
                print(f"Summarization failed for response: {summarized_content}") 
                raise ValueError(f"Could not parse the summarized response {summarized_content}")

        except OpenAIError as e:
            raise Exception(f"OpenAI Error: {e}")
