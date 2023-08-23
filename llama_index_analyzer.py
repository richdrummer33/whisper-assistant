import openai
import os
import winsound
import tkinter as tk
import tkinter.filedialog as filedialog
from llama_index import VectorStoreIndex, SimpleDirectoryReader, global_service_context, PromptHelper, LLMPredictor

###########################################
##############################################################################################################
###########################################
## USE THIS: https://gpt-index.readthedocs.io/en/latest/examples/agent/openai_agent_with_query_engine.html
# https://github.com/jerryjliu/llama_index/issues/3366
# https://stackoverflow.com/questions/76796764/ai-related-questions-on-openai-and-llama-llm-usage
###########################################
##############################################################################################################
###########################################

# enum for warnign or success sfx notification
class NotificationType:
    WARNING = "C:\\Windows\\Media\\Windows Exclamation.wav"
    SUCCESS = "C:\\Windows\\Media\\Speech On.wav"

# 1. Initialize LlamaIndex and OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY") # Set your OpenAI API key as an environment variable
index = None
#llm_predictor = LLMPredictor(llm=openai(temperature=0.7, model_name="gpt-3.5-turbo", max_tokens=8192))
# service_context = ServiceContext.from_defaults(llm_predictor=llm_predictor)

def play_notification_sound(notification_type):
    if notification_type == NotificationType.WARNING:
        sound_path = NotificationType.WARNING
    elif notification_type == NotificationType.SUCCESS:
        sound_path = NotificationType.SUCCESS
    winsound.PlaySound(sound_path, winsound.SND_FILENAME)


# 2. Ingest Files into LlamaIndex bty selecting file or folder with tkinter
def     ingest_files_to_llama(directory_path):
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
        print("...selected file " + str(file_path))
        
        reader = SimpleDirectoryReader(input_files=[str(file_path)])

    elif option == "2":
        root = tk.Tk()
        root.withdraw()
        directory_path = filedialog.askdirectory()
        root.destroy()
        print("...selected dir " + str(directory_path))
        required_exts = [".md", ".py", ".txt"]

        reader = SimpleDirectoryReader(input_dir="C:/Git/voice-clone-bot/", required_exts = required_exts, recursive=True)
    
    try:
        documents = reader.load_data()
        index = VectorStoreIndex.from_documents(documents)
        play_notification_sound(NotificationType.SUCCESS)
        print("...successfully ingested files into LlamaIndex")
        # index.storage_context.persist() # save to disk
    except:
        play_notification_sound(NotificationType.WARNING)
        print("...failed to ingest files into LlamaIndex")
        

# 4. Query GPT to Summarize or Answer Questions about the Indexed Content
def query_gpt(query):
    # Use LlamaIndex to get relevant document snippets for the question
    #kwargs = {
    #    "service_context": "gpt-4",
    #}
    query_engine = index.as_query_engine(streaming=True) # , service_context=service_context) #(kwargs={'model': 'gpt-4'})
    streaming_response = query_engine.query(query)
    streaming_response.print_response_stream()


# Example usage:
ingest_files_to_llama("/path/to/your/directory")
query = input("What do you want to do with this data? ")
response = query_gpt(query)
print(response)
