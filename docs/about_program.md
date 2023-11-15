# What is NER
NER, or Named Entity Recognition, is a natural language processing (NLP) technique used to identify and classify specific named entities within a text. These named entities can include names of people, organizations, locations, dates, monetary values, and more. The primary goal of NER is to extract and categorize this structured information from unstructured text data, enabling machines to understand and work with text more effectively.

In this program we use a hybrid approach, which means we combine two different methods: machine learning-based and dictionary-based.

For the machine learning-based approach, we use a Python library called Spacy. Spacy is designed for natural language processing (NLP) tasks, including named entity recognition.

For the dictionary-based approach, we use the Levenshtein algorithm to search for entities in a pre-built dictionary. This dictionary helps us recognize and extract specific information from the receipts.

---
# How The Program Works
```
 Input: receipt image

           │
           ▼

    Text Extraction
       Vision OCR

           │
           ▼

Named Entity Recognition
       NLP Based

           │
           ▼

  If Field is Filled?

     True  │  False
           │
          ┌┴──► Named Entity Recognition
          │         Dictionary Based
          │
          │              │
          ▼              │
                         │
     Data Cleaning ◄─────┘

           │
           ▼

         Finish
```