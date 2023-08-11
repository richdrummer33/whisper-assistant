import openai
import os
import tkinter as tk
import tkinter.filedialog as filedialog
from llama_index import VectorStoreIndex, SimpleDirectoryReader, global_service_context


# 1. Initialize LlamaIndex and OpenAI
openai.api_key = 'OPENAI_API_KEY' # Set your OpenAI API key
index = None

# 2. Ingest Files into LlamaIndex bty selecting file or folder with tkinter
def ingest_files_to_llama(directory_path):
    global index
    option = -1
    
    # query user enter option in console
    while option != "1" and option != "2":
        print("Select a file or folder to ingest into LlamaIndex")
        print("1. Select a file")
        print("2. Select a folder")
        option = input("Enter option: ")
    
    if option == "1":
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename()
        root.destroy()
        reader = SimpleDirectoryReader(input_files=[file_path])

    elif option == "2":
        root = tk.Tk()
        root.withdraw()
        directory_path = filedialog.askdirectory()
        root.destroy()
        documents = SimpleDirectoryReader(input_dir=directory_path, recursive=True)

    index = VectorStoreIndex.from_documents(documents)
    # index.storage_context.persist() # save to disk

# 4. Query GPT to Summarize or Answer Questions about the Indexed Content
def query_gpt(query):
    # Use LlamaIndex to get relevant document snippets for the question
    kwargs = {
        "service_context": "gpt-4",
    }
    query_engine = index.as_query_engine(kwargs) #(kwargs={'model': 'gpt-4'})
    query_engine.query("<question_text>?")

    
    # Combine snippets to create the prompt for GPT
    prompt = f"Based on the following information: {'. '.join(relevant_snippets)}, {query}"
    
    gpt_query_params = {
        'model': 'gpt-4',
        'messages': [
            {"role": "user", "content":  prompt}
        ]
    }
    
    # Query OpenAI GPT
    response = openai.ChatCompletion.create(**gpt_query_params)
    
    return response.choices[0].text.strip()

# Example usage:
ingest_files_to_llama("/path/to/your/directory")
query = input("What do you want to do with this data? ")
response = query_gpt(query)
print(response)
