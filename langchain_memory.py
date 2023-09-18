from langchain.prompts.prompt import PromptTemplate    # can override default prompt
from langchain.memory import ConversationBufferMemory  # ConversationSummaryMemory
from langchain.callbacks.base import BaseCallbackHandler
from langchain.chains import ConversationChain
from langchain.chat_models import ChatOpenAI
import os
import openai

# REFS:
# Memory: https://sonery.medium.com/4-memory-types-of-langchain-to-enhance-the-performance-of-llms-bda339d2e904
# Prompt template overriding: https://python.langchain.com/docs/modules/memory/conversational_customization


# on ctrl-c pressed, cancel the conversation
def signal_handler(sig, frame):
    global conversation
    print("...exiting conversation")
    conversation.cancel()
    sys.exit(0)


# main
if __name__ == "__main__":
    # initialize open AI
    openai.api_key = os.getenv("OPENAI_API_KEY")
    llm = ChatOpenAI(temperature=0.6, model="gpt-3.5-turbo",
                     max_tokens=250, streaming=False)

    # define prompt template
    # + "The captain is thus extremely frightened of the sea, and obviously afraid of the sea as well. In nearly every response, the Captain slips in a new tidbit of his harrowing tale about the shark and the sea.
    prompt_template = """The following is a friendly conversation between a human and the captain of a sailing vessel.
    + The captain uses sailing analogies and terms to answer any question asked. The captain lost his left nut to a shark while swimming in the ocean, and thus is deathly afraid of the sea, but does everything he can to mask it with toughness. 
    + In every response, he elaborately embellishes the tale of his harrowing duel with a shark to fortify his rugged exterior; yet, his deathly fear of the sea betrays him, causing him to falter over his words and inadvertently unveil his deep-seated vulnerabilities. "
   
    Current conversation:
    {history}
    Human: {input}
    Ship's Captain:"""

    prompt = PromptTemplate(
        input_variables=["history", "input"], template=prompt_template)

    # define conversation chain
    conversation = ConversationChain(
        prompt=prompt,
        llm=llm,
        verbose=False,
        ### CHANGE TO SUMMARY MEMORY ###
        memory=ConversationBufferMemory(ai_prefix="Ship's Captain"),
        ### CHANGE TO SUMMARY MEMORY ###
    )

    # take in user input in the console
    while True:

        user_input = input(
            "What do you want to say to, or ask, the Ship's Captain?\n> ")
        if user_input == "exit":
            break

        print("The captain ponders your query...")
        response = conversation.predict(input=user_input)
        print(response)
