import fitz
import openai
import nltk
from nltk.tokenize import sent_tokenize
from io import StringIO
import json
import os
import time

#nltk.download('punkt')

def open_file(filepath):
  with open(filepath, "r", encoding='utf-8') as infile:
    return infile.read()

openai.api_key = os.getenv("OPENAI_API_KEY")

def read_pdf(filename):
  context = ""
  
  # Open the PDF file
  with fitz.open(filename) as pdf_file:
  
    # Get the number of pages in the PDF file
    num_pages = pdf_file.page_count
    
    # Loop through each page in the PDF file
    for page_num in range(num_pages):
      
      # Get the current page
      page = pdf_file[page_num]
      
      # Get the text from the current page
      page_text = page.get_text()
      
      # Append the text to context
      context += page_text
  return context

def split_text(text, chunk_size=5000):
  """
  Splits the given text into chunks of approximately the specified chunk size.
  
  Args:
  text (str): The text to split.
  
  chunk_size (int): The desired size of each chunk (in characters).
  
  Returns:
  List[str]: A list of chunks, each of approximately the specified chunk size.
  """
  
  chunks = []
  current_chunk = StringIO()
  current_size = 0
  sentences = sent_tokenize(text)
  for sentence in sentences:
    sentence_size = len(sentence)
    if sentence_size > chunk_size:
      while sentence_size > chunk_size:
        chunk = sentence[:chunk_size]
        chunks.append(chunk)
        sentence = sentence[chunk_size:]
        sentence_size -= chunk_size
        current_chunk = StringIO()
        current_size = 0
    if current_size + sentence_size < chunk_size:
      current_chunk.write(sentence)
      current_size += sentence_size
    else:
      chunks.append(current_chunk.getvalue())
      current_chunk = StringIO()
      current_chunk.write(sentence)
      current_size = sentence_size
  if current_chunk:
     chunks.append(current_chunk.getvalue())
  return chunks
  

def gpt3_completion(prompt, engine='text-davinci-003', temp=0.5, top_p=0.3, tokens=1000):
    print("GPT prompting")
    prompt = prompt.encode(encoding='ASCII',errors='ignore').decode()
    try:
        response = openai.Completion.create(
        engine=engine,
        prompt=prompt,
        temperature=temp,
        top_p=top_p,
        max_tokens=tokens
        )
        return response.choices[0].text.strip()
    except Exception as oops:
        return "GPT-3 error: %s" % oops


def summrize(documnet):
  
  # Calling the split function to split text
  chunks = split_text(documnet)
  print ("Number of chunks: ", len(chunks))
  summaries = []
  for chunk in chunks:
    prompt = "I am an engineer helping a writer create a beleivable science fiction story. Please summarize the following document for me, in such a way that I can deduce the technical elements - so that I can best advise him to create a believable tale. \n"
    summary = gpt3_completion(prompt + chunk)

    if summary.startswith("GPT-3 error:"):
        print("GPT-3 error")
        continue

    summaries.append(summary)
  return ''.join(summaries)


#read the pdf file
document = read_pdf("C:/Users/richd/Downloads/SPACESHIP through _DO NOTHING_.pdf")

# Call the summrize function with the document as input
summary = summrize(document)

# Print the summary
print(summary)
