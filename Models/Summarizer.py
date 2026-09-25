from transformers import pipeline



summarizer = pipeline(task="summarization")
ModelAndTokenizer = pipeline(task="question-answering")

while True:
    print("Enter a paragraph here:") #this will eventually read in from pdfs/markdowns 
    print("Type 'quit' at any prompt to exit.\n")
    
    UserParagraph = input("Enter paragraph (or 'quit'): ").strip()
    
    if UserParagraph.lower() == "quit":  
        print("Exiting.....")
        break


    if not UserParagraph:
        print("Enter some text here.\n")
        continue
    
    #summarise section 
    print("\nSummarising...\n")
    summary_result = summarizer(UserParagraph, max_length=80, min_length=20, do_sample=False) #this is only small amount of text, will trial large and small sections
    summary = summary_result[0]["summary_text"] 
    print(f"Summary: {summary}\n")
    #summarise then rewrite into repository 

    #QnA Section 
    #this isn't really needed but it was apart of the lab that im using to refresh my memory on making a summarizer
    print("You can now ask questions about the paragraph.")
    print("Type 'new' for a new paragraph, or 'quit' to exit.\n")

    while True:
        question = input("Enter question (or 'new' / 'quit'): ").strip()

        if question.lower() == "quit":
            print("Exiting.....")
            exit()
        if question.lower() == "new":
            break
        if not question:
            print("Please enter a question.\n")
            continue

            #print confidence and answer. 
        result = ModelAndTokenizer(question=question, context=UserParagraph)
        print(f"\nAnswer:     {result['answer']}")
        print(f"Confidence: {result['score']:.2%}\n")   

        #currently two paths i can take this, i can either scrap websites (this will take a bit more research and trial and error)
        #or i can download the files and then read from a txt/document and parse the paths to each pdf/md file which then reads them in
        #Curling or scraping from the web will be tricky since i'll need to filter out all the html or random other things that will come along with the information
        #i.e i could filter out all html by ignoring anything in <>. 
