import os
import winsound
import tkinter as tk
import tkinter.filedialog as filedialog
from llama_index import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    LLMPredictor,
    ServiceContext
)
from llama_index.llms import OpenAI

# Prettier output:
# from IPython.display import Markdown, display

##############################################################################################################
# How to use custom llm settings (gpt-4, hugging face): https://gpt-index.readthedocs.io/en/latest/core_modules/model_modules/llms/usage_custom.html
# USE THIS: https://gpt-index.readthedocs.io/en/latest/examples/agent/openai_agent_with_query_engine.html
# https://github.com/jerryjliu/llama_index/issues/3366
# https://stackoverflow.com/questions/76796764/ai-related-questions-on-openai-and-llama-llm-usage
##############################################################################################################


# enum for warnign or success sfx notification
class NotificationType:
    WARNING = "C:\\Windows\\Media\\Windows Exclamation.wav"
    SUCCESS = "C:\\Windows\\Media\\Speech On.wav"


# 1. Initialize LlamaIndex and OpenAI
OpenAI.api_key = os.getenv("OPENAI_API_KEY")
print("...initialized OpenAI API key: " + OpenAI.api_key)
index = None


def play_notification_sound(notification_type):
    if notification_type == NotificationType.WARNING:
        sound_path = NotificationType.WARNING
    elif notification_type == NotificationType.SUCCESS:
        sound_path = NotificationType.SUCCESS
    winsound.PlaySound(sound_path, winsound.SND_FILENAME)


# 2. Ingest Files into LlamaIndex bty selecting file or folder with tkinter
def ingest_files_to_llama():
    global index
    option = -1

    # query user enter option in console
    while option != "1" and option != "2":
        print("Select a file or folder to ingest into LlamaIndex")
        print("1. Select a file")
        print("2. Select a folder")
        option = input("Enter option: ")

    # ingest file
    if option == "1":
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename()
        root.destroy()
        print("...selected file " + str(file_path))

        reader = SimpleDirectoryReader(input_files=[str(file_path)])

    # ingest folder
    elif option == "2":
        root = tk.Tk()
        root.withdraw()
        directory_path = filedialog.askdirectory()
        root.destroy()
        print("...selected dir " + str(directory_path))
        required_exts = [".md", ".py", ".txt"]

        reader = SimpleDirectoryReader(
            input_dir=directory_path, required_exts=required_exts, recursive=True)

    # define LLM
    llm = OpenAI(temperature=0.1, model="gpt-4")
    print("...defined LLM")
    service_context = ServiceContext.from_defaults(llm=llm)
    print("...created service context")

    # ingest files into LlamaIndex
    documents = reader.load_data()
    print(f"Loaded {len(documents)} docs")
    index = VectorStoreIndex.from_documents(
        documents, service_context=service_context)
    print("...successfully ingested files into LlamaIndex")
    play_notification_sound(NotificationType.SUCCESS)

    # save to disk
    # index.storage_context.persist()


# Docs query, e.g. "What is the meaning of life?"
def query_gpt(query):
    query_engine = index.as_query_engine(streaming=True)
    streaming_response = query_engine.query(query)
    streaming_response.print_response_stream()


# Main function
if __name__ == "__main__":
    ingest_files_to_llama()
    query = input("What do you want to do with this data? ")
    response = query_gpt(query)
    print(response)
